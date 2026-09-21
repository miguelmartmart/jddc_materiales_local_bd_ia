"""Selector de proyectos: búsqueda, estado y paginación con parámetros SQL."""


def search(driver_factory, search="", offset=0, limit=15):
    offset, limit = max(0, int(offset)), max(1, min(int(limit), 50))
    needle = str(search or "").strip()
    where = " WHERE CODIGO CONTAINING ? OR NOMBRE CONTAINING ?" if needle else ""
    params = (needle, needle) if needle else None
    driver = driver_factory()
    try:
        count = driver.execute_query("SELECT COUNT(*) AS N FROM PROYECTOS" + where, params)
        rows = driver.execute_query(
            f"SELECT FIRST {limit} SKIP {offset} CODIGO,NOMBRE,FINOBRA FROM PROYECTOS" + where + " ORDER BY CODIGO", params)
        total = int(count[0]["N"])
        return {"ok": True, "valores": [{"id": str(r["CODIGO"]), "desc": r.get("NOMBRE") or "",
                    "estado": "Finalizado" if r.get("FINOBRA") == "T" else "No finalizado" if r.get("FINOBRA") == "F" else "Estado desconocido"} for r in rows],
                "total": total, "offset": offset, "limit": limit, "hay_mas": offset + len(rows) < total, "busqueda": needle}
    finally:
        driver.disconnect()
