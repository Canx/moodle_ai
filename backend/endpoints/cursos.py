from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models_db import CursoDB, CuentaMoodleDB, TareaDB, EntregaDB
from database import get_db
from scraper import get_tareas_de_curso, login_moodle
from playwright.sync_api import sync_playwright

router = APIRouter()

@router.get("/api/cursos")
def obtener_cursos(db: Session = Depends(get_db)):
    cursos = db.query(CursoDB).all()
    return [{"id": c.id, "nombre": c.nombre} for c in cursos]

@router.post("/api/cursos/{curso_id}/sincronizar_tareas")
def sincronizar_tareas_curso(curso_id: int, db: Session = Depends(get_db)):
    # Obtener cuenta asociada al curso
    curso = db.query(CursoDB).filter(CursoDB.id == curso_id).first()
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == curso.cuenta_id).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    usuario = cuenta.usuario_moodle
    contrasena = cuenta.contrasena_moodle
    moodle_url = cuenta.moodle_url
    url_curso = curso.url
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            login_moodle(page, moodle_url, usuario, contrasena)
            curso_obj = {"nombre": curso.nombre, "url": curso.url}
            tareas = get_tareas_de_curso(browser, page, moodle_url, cuenta.id, curso_obj)
            # Borrar tareas previas del curso
            db.query(TareaDB).filter(TareaDB.curso_id == curso_id).delete()
            db.commit()
            # Borrar entregas antiguas de todas las tareas de este curso
            tarea_ids = [t.id for t in db.query(TareaDB).filter(TareaDB.curso_id == curso_id).all()]
            if tarea_ids:
                db.query(EntregaDB).filter(EntregaDB.tarea_id.in_(tarea_ids)).delete(synchronize_session=False)
                db.commit()
            for tarea in tareas:
                # Determinar el estado de la tarea
                entregas = tarea.get('entregas_pendientes', [])
                if not entregas:
                    estado = 'sin_entregas'
                elif any(e.get('estado', '').lower().startswith('enviado') or e.get('estado', '').lower().startswith('pendiente') for e in entregas):
                    estado = 'pendiente_calificar'
                else:
                    estado = 'sin_pendientes'
                nueva_tarea = TareaDB(
                    cuenta_id=cuenta.id,
                    curso_id=curso_id,
                    tarea_id=tarea["tarea_id"],
                    titulo=tarea["titulo"],
                    estado=estado,
                    calificacion_maxima=tarea.get("calificacion_maxima")
                )
                db.add(nueva_tarea)
                db.commit()
                db.refresh(nueva_tarea)
                print(f"[DEBUG] Entregas pendientes para tarea '{tarea['titulo']}': {len(tarea.get('entregas_pendientes', []))}")
                # Guardar entregas en la tabla entregas (si las hay)
                for entrega in tarea.get('entregas_pendientes', []):
                    nueva_entrega = EntregaDB(
                        tarea_id=nueva_tarea.id,
                        alumno_id=entrega.get('alumno_id'),
                        fecha_entrega=entrega.get('fecha_entrega'),
                        file_url=entrega.get('archivos', [{}])[0].get('url') if entrega.get('archivos') else None,
                        file_name=entrega.get('archivos', [{}])[0].get('nombre') if entrega.get('archivos') else None,
                        estado=entrega.get('estado'),
                        nombre=entrega.get('nombre')
                    )
                    db.add(nueva_entrega)
                db.commit()
            browser.close()
        return {"mensaje": "Sincronización completada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al sincronizar tareas: {e}")

@router.get("/api/cursos/{curso_id}/tareas")
def obtener_tareas_curso(curso_id: int, db: Session = Depends(get_db)):
    tareas = db.query(TareaDB).filter(
        TareaDB.curso_id == curso_id,
        TareaDB.oculto == False
    ).order_by(TareaDB.id.desc()).all()
    # Incluir count de entregas pendientes por tarea
    result = []
    for t in tareas:
        # contar solo entregas con archivo o contenido de texto
        entregadas = db.query(EntregaDB).filter(
            EntregaDB.tarea_id == t.id,
            or_(EntregaDB.file_url != None, EntregaDB.contenido != None)
        ).count()
        pendientes = db.query(EntregaDB).filter(EntregaDB.tarea_id == t.id, EntregaDB.nota == None).count()
        result.append({
            "id": t.id,
            "tarea_id": t.tarea_id,
            "titulo": t.titulo,
            "descripcion": t.descripcion,
            "estado": t.estado,
            "entregadas": entregadas,
            "pendientes": pendientes
        })
    return result

@router.get("/api/cursos/{curso_id}/tareas/ocultas")
def obtener_tareas_ocultas_curso(curso_id: int, db: Session = Depends(get_db)):
    tareas = db.query(TareaDB).filter(
        TareaDB.curso_id == curso_id,
        TareaDB.oculto == True
    ).order_by(TareaDB.id.desc()).all()
    return [{"id": t.id, "tarea_id": t.tarea_id, "titulo": t.titulo, "descripcion": t.descripcion, "estado": t.estado} for t in tareas]

@router.post("/api/cursos/{curso_id}/ocultar")
def ocultar_curso(curso_id: int, db: Session = Depends(get_db)):
    curso = db.query(CursoDB).filter(CursoDB.id == curso_id).first()
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    curso.oculto = True
    db.commit()
    return {"ok": True, "oculto": True}

@router.post("/api/cursos/{curso_id}/mostrar")
def mostrar_curso(curso_id: int, db: Session = Depends(get_db)):
    curso = db.query(CursoDB).filter(CursoDB.id == curso_id).first()
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    curso.oculto = False
    db.commit()
    return {"ok": True, "oculto": False}