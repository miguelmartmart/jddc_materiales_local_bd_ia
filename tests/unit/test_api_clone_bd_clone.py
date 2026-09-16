"""test_api_clone_bd_clone.py — Tests unitarios API Clone y BD Clone. Sin BD, sin IA."""
import pytest
from unittest.mock import MagicMock, patch


class TestApiCloneQueries:
    """BLOQUE A — queries.py"""

    def test_17_clases_definidas(self):
        from backend.modules.api_clone.queries import ALL_CLASES
        assert len(ALL_CLASES) == 17

    def test_todas_clases_tienen_tabla(self):
        from backend.modules.api_clone.queries import CLASE_TABLA_MAP, ALL_CLASES
        for clase in ALL_CLASES:
            assert clase in CLASE_TABLA_MAP

    def test_tabla_map_4_elementos(self):
        from backend.modules.api_clone.queries import CLASE_TABLA_MAP
        for clase, info in CLASE_TABLA_MAP.items():
            assert len(info) == 4, f"'{clase}': esperados 4 elementos"

    def test_obralin_es_tabla_proordutil(self):
        from backend.modules.api_clone.queries import CLASE_TABLA_MAP
        assert CLASE_TABLA_MAP["proordutil"][0] == "OBRALIN"

    def test_repara_es_tabla_reporden(self):
        from backend.modules.api_clone.queries import CLASE_TABLA_MAP
        assert CLASE_TABLA_MAP["reporden"][0] == "REPARA"

    def test_repcar_es_tabla_repordutil(self):
        from backend.modules.api_clone.queries import CLASE_TABLA_MAP
        assert CLASE_TABLA_MAP["repordutil"][0] == "REPCAR"
        assert CLASE_TABLA_MAP["repordutil"][1] == "CODREPARA"

    def test_doccab_filtros_tipo(self):
        from backend.modules.api_clone.queries import CLASE_WHERE
        assert CLASE_WHERE["docalbcom"] == "TIPO = 2"
        assert CLASE_WHERE["docfaccom"] == "TIPO = 3"
        assert CLASE_WHERE["docpedcom"] == "TIPO = 11"

    def test_tablas_inexistentes_eliminadas(self):
        """PARTPROYE, PREUTILLIN, PREPREVLIN, RABUTILLIN no existen en BD JDDC"""
        from backend.modules.api_clone.queries import CLASE_TABLA_MAP
        prohibidas = {"PARTPROYE", "PREUTILLIN", "PREPREVLIN", "RABUTILLIN"}
        for clase, info in CLASE_TABLA_MAP.items():
            assert info[0] not in prohibidas, f"'{clase}' usa tabla inexistente '{info[0]}'"

    def test_riesgos_correctos(self):
        from backend.modules.api_clone.queries import RIESGO_OPERACION
        assert RIESGO_OPERACION["browse"] == 0
        assert RIESGO_OPERACION["read"] == 0
        assert RIESGO_OPERACION["cancel"] == 0
        assert RIESGO_OPERACION["new"] == 1
        assert RIESGO_OPERACION["edit"] == 1
        assert RIESGO_OPERACION["write"] == 2
        assert RIESGO_OPERACION["imputaPro"] == 2
        assert RIESGO_OPERACION["delete"] == 3

    def test_confirmaciones_correctas(self):
        from backend.modules.api_clone.queries import CONFIRMACION_REQUERIDA
        assert CONFIRMACION_REQUERIDA[2] == "CONFIRMAR ESCRITURA"
        assert CONFIRMACION_REQUERIDA[3] == "CONFIRMAR BORRADO DEFINITIVO"
        assert CONFIRMACION_REQUERIDA[0] == ""

    def test_ops_proyectos_segun_doc_mpyme(self):
        from backend.modules.api_clone.queries import CLASE_OPERACIONES
        ops = set(CLASE_OPERACIONES["proyectos"])
        assert {"browse","read","new","edit","write","cancel"}.issubset(ops)

    def test_ops_reporden_segun_doc(self):
        from backend.modules.api_clone.queries import CLASE_OPERACIONES
        ops = set(CLASE_OPERACIONES["reporden"])
        assert {"browse","read","new","edit","write","cancel"}.issubset(ops)

    def test_ops_docalbcom_con_imputapro(self):
        from backend.modules.api_clone.queries import CLASE_OPERACIONES
        ops = set(CLASE_OPERACIONES["docalbcom"])
        assert "imputaPro" in ops
        assert "imputaRep" in ops

    def test_tipostrabajo_solo_browse(self):
        from backend.modules.api_clone.queries import CLASE_OPERACIONES
        assert CLASE_OPERACIONES["tipostrabajo"] == ["browse"]

    def test_cols_browse_proordutil_reales(self):
        from backend.modules.api_clone.queries import CLASE_COLS_BROWSE
        cols = CLASE_COLS_BROWSE["proordutil"]
        assert "CODPROYECTO" in cols and "FECHA" in cols

    def test_param_columna_correcto(self):
        from backend.modules.api_clone.queries import PARAM_A_COLUMNA
        assert PARAM_A_COLUMNA["proordutil"]["codProyecto"] == "CODPROYECTO"
        assert PARAM_A_COLUMNA["repordutil"]["codOrden"] == "CODREPARA"

    def test_partidas_requiere_codproyecto(self):
        from backend.modules.api_clone.queries import CLASE_PARAM_REQUERIDO
        assert CLASE_PARAM_REQUERIDO["partidas"] == "codProyecto"
        assert CLASE_PARAM_REQUERIDO["proyectos"] is None


class TestApiCloneProteccionEscritura:
    """BLOQUE B — Proteccion de escritura (3 niveles)"""

    def _svc(self):
        from backend.modules.api_clone.service import ApiCloneService
        return ApiCloneService()

    def test_estado_inicial_solo_lectura(self):
        svc = self._svc()
        assert svc.modo_escritura is False and svc.session_escritura is False

    def test_lectura_siempre_ok(self):
        svc = self._svc()
        for op in ["browse","read","permiso","info","cancel"]:
            assert svc._verificar_escritura(op) is None

    def test_new_sin_modo_bloqueado(self):
        svc = self._svc()
        r = svc.new("proyectos")
        assert r["estado"] == "falla" and "BLOQUEADO" in r["error"]

    def test_paso1_incorrecto_falla(self):
        assert self._svc().activar_modo_escritura("mal")["ok"] is False

    def test_paso1_correcto(self):
        svc = self._svc()
        r = svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        assert r["ok"] is True and svc.modo_escritura is True and svc.session_escritura is False

    def test_paso2_sin_paso1_falla(self):
        assert self._svc().activar_session_escritura("CONFIRMAR ESCRITURA")["ok"] is False

    def test_paso2_incorrecto_falla(self):
        svc = self._svc(); svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        assert svc.activar_session_escritura("mal")["ok"] is False

    def test_paso2_correcto(self):
        svc = self._svc(); svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        r = svc.activar_session_escritura("CONFIRMAR ESCRITURA")
        assert r["ok"] is True and svc.session_escritura is True

    def test_desactivar_limpia_todo(self):
        svc = self._svc()
        svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        svc.activar_session_escritura("CONFIRMAR ESCRITURA")
        svc._objetos_temporales["X"] = {"clase":"x","data":{},"ts":""}
        r = svc.desactivar_escritura()
        assert r["ok"] and not svc.modo_escritura and not svc.session_escritura
        assert len(svc._objetos_temporales) == 0 and r["objetos_temporales_descartados"] == 1

    def test_new_con_paso1_crea_temporal(self):
        svc = self._svc(); svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        r = svc.new("proyectos")
        assert r["estado"] == "ok"
        oid = r["data"]["objectid"]
        assert oid.startswith("TMP_PROYECTOS_") and oid in svc._objetos_temporales

    def test_new_clase_desconocida_falla(self):
        svc = self._svc(); svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        assert self._svc().activar_modo_escritura("ACTIVAR ESCRITURA") and True
        svc2 = self._svc(); svc2.activar_modo_escritura("ACTIVAR ESCRITURA")
        r = svc2.new("clase_inexistente")
        assert r["estado"] == "falla"

    def test_edit_sin_new_falla(self):
        svc = self._svc(); svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        r = svc.edit("proyectos","TMP_FAKE",{"x":1})
        assert r["estado"] == "falla" and "no encontrado" in r["error"]

    def test_edit_actualiza_datos(self):
        svc = self._svc(); svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        oid = svc.new("proyectos")["data"]["objectid"]
        svc.edit("proyectos", oid, {"NOMBRE":"Test","CLIENTE":999})
        d = svc._objetos_temporales[oid]["data"]
        assert d["NOMBRE"] == "Test" and d["CLIENTE"] == 999

    def test_cancel_elimina_temporal(self):
        svc = self._svc(); svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        oid = svc.new("proyectos")["data"]["objectid"]
        svc.cancel("proyectos", oid)
        assert oid not in svc._objetos_temporales

    def test_cancel_inexistente_no_falla(self):
        assert self._svc().cancel("proyectos","FAKE")["estado"] == "ok"

    def test_write_sin_paso2_bloqueado(self):
        svc = self._svc(); svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        oid = svc.new("proyectos")["data"]["objectid"]
        r = svc.write("proyectos", oid, {}, "CONFIRMAR ESCRITURA")
        assert r["estado"] == "falla" and "BLOQUEADO" in r["error"]

    def test_write_confirmacion_incorrecta(self):
        svc = self._svc()
        svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        svc.activar_session_escritura("CONFIRMAR ESCRITURA")
        oid = svc.new("proyectos")["data"]["objectid"]
        r = svc.write("proyectos", oid, {"NOMBRE":"x"}, "mal")
        assert r["estado"] == "falla" and "BLOQUEADO" in r["error"]

    def test_verificar_con_todos_pasos_ok(self):
        svc = self._svc()
        svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        svc.activar_session_escritura("CONFIRMAR ESCRITURA")
        assert svc._verificar_escritura("write","CONFIRMAR ESCRITURA") is None

    def test_imputa_accion_invalida(self):
        svc = self._svc()
        svc.activar_modo_escritura("ACTIVAR ESCRITURA")
        svc.activar_session_escritura("CONFIRMAR ESCRITURA")
        r = svc.imputa("docalbcom","123","MALA","x","","F","CONFIRMAR ESCRITURA")
        assert r["estado"] == "falla"


class TestApiCloneLectura:
    """BLOQUE C — browse/read/permiso/info mockeando driver"""

    def _svc(self):
        from backend.modules.api_clone.service import ApiCloneService
        return ApiCloneService()

    @patch("backend.modules.api_clone.service._get_driver")
    def test_permiso_valido_devuelve_n(self, mock_get):
        mock_drv = MagicMock()
        mock_drv.execute_query.return_value = [{"N": 1213}]
        mock_drv.disconnect = MagicMock()
        mock_get.return_value = mock_drv
        r = self._svc().permiso("proyectos")
        assert r["estado"] == "ok"
        assert r["data"]["n_registros"] == 1213
        assert r["data"]["tabla_firebird"] == "PROYECTOS"

    def test_permiso_clase_desconocida_falla(self):
        assert self._svc().permiso("fake")["estado"] == "falla"

    @patch("backend.modules.api_clone.service._get_driver")
    def test_browse_devuelve_items_y_total(self, mock_get):
        mock_drv = MagicMock()
        def exe(sql):
            return [{"N": 1213}] if "COUNT" in sql.upper() else [{"CODIGO":"45871","NOMBRE":"P"}]
        mock_drv.execute_query.side_effect = exe
        mock_drv.disconnect = MagicMock()
        mock_get.return_value = mock_drv
        r = self._svc().browse("proyectos", {})
        assert r["estado"] == "ok" and r["data"]["total"] == 1213

    def test_browse_requiere_param_da_aviso(self):
        r = self._svc().browse("partidas", {})
        assert r["estado"] == "ok" and r["data"]["items"] == []

    @patch("backend.modules.api_clone.service._get_driver")
    def test_browse_docalbcom_filtra_tipo2(self, mock_get):
        mock_drv = MagicMock()
        def exe(sql):
            return [{"N": 5}] if "COUNT" in sql.upper() else [{"CODIGO":1,"TIPO":2}]
        mock_drv.execute_query.side_effect = exe
        mock_drv.disconnect = MagicMock()
        mock_get.return_value = mock_drv
        self._svc().browse("docalbcom", {})
        calls = [str(c) for c in mock_drv.execute_query.call_args_list]
        assert any("TIPO = 2" in c for c in calls)

    @patch("backend.modules.api_clone.service._get_driver")
    def test_read_valido(self, mock_get):
        mock_drv = MagicMock()
        mock_drv.execute_query.return_value = [{"CODIGO":"45871","NOMBRE":"T"}]
        mock_drv.disconnect = MagicMock()
        mock_get.return_value = mock_drv
        r = self._svc().read("proyectos","45871")
        assert r["estado"] == "ok" and r["data"]["CODIGO"] == "45871"

    def test_read_sin_objectid_falla(self):
        assert self._svc().read("proyectos","")["estado"] == "falla"

    @patch("backend.modules.api_clone.service._get_driver")
    def test_read_no_encontrado(self, mock_get):
        mock_drv = MagicMock()
        mock_drv.execute_query.return_value = []
        mock_drv.disconnect = MagicMock()
        mock_get.return_value = mock_drv
        r = self._svc().read("proyectos","FAKE")
        assert r["estado"] == "falla"

    def test_where_docalbcom_tipo2(self):
        assert "TIPO = 2" in self._svc()._where("docalbcom", {})

    def test_where_proyectos_filtro(self):
        where = self._svc()._where("proyectos", {"codProyecto":"45871"})
        assert "45871" in where and "CODIGO" in where

    def test_status_tiene_escritura(self):
        st = self._svc().get_status()
        assert "modo_escritura" in st and "session_escritura" in st

    def test_catalogue_tiene_riesgos(self):
        cat = self._svc().get_catalogue()
        assert "riesgo_operaciones" in cat and "confirmaciones_requeridas" in cat


class TestBdCloneService:
    """BLOQUE D — BD Clone service"""

    def _svc(self):
        from backend.modules.bd_clone.service import BDCloneService
        return BDCloneService()

    def test_estado_inicial(self):
        assert self._svc().modo_escritura is False

    def test_activar_escritura_incorrecto(self):
        assert self._svc().activar_escritura("mal")["ok"] is False

    def test_activar_escritura_correcto(self):
        svc = self._svc()
        r = svc.activar_escritura("ACTIVAR ESCRITURA BD")
        assert r["ok"] is True and svc.modo_escritura is True

    def test_desactivar(self):
        svc = self._svc()
        svc.activar_escritura("ACTIVAR ESCRITURA BD")
        r = svc.desactivar_escritura()
        assert r["ok"] and not svc.modo_escritura

    def test_sql_vacio_falla(self):
        assert self._svc().ejecutar_sql("")["ok"] is False

    def test_escritura_sin_modo_bloqueado(self):
        svc = self._svc()
        for sql in ["INSERT INTO T VALUES(1)","UPDATE T SET X=1","DELETE FROM T"]:
            r = svc.ejecutar_sql(sql)
            assert r["ok"] is False and r.get("bloqueado") is True

    def test_inyectar_first_simple(self):
        from backend.modules.bd_clone.service import BDCloneService
        r = BDCloneService._inyectar_first("SELECT * FROM T", 50)
        assert "FIRST 50" in r

    def test_inyectar_first_ya_tiene(self):
        from backend.modules.bd_clone.service import BDCloneService
        sql = "SELECT FIRST 10 * FROM T"
        assert BDCloneService._inyectar_first(sql, 50) == sql

    def test_add_history(self):
        svc = self._svc()
        svc._add_history("SELECT 1", ok=True, ms=10, n_rows=1)
        h = svc.get_history(1)
        assert len(h) == 1 and h[0]["ok"] is True

    def test_clear_history(self):
        svc = self._svc()
        svc._add_history("SELECT 1", ok=True, ms=1, n_rows=1)
        svc.clear_history()
        assert svc.get_history() == []

    def test_historial_max_size(self):
        from backend.modules.bd_clone.service import MAX_HISTORY, BDCloneService
        svc = BDCloneService()
        for i in range(MAX_HISTORY + 5):
            svc._add_history(f"S{i}", ok=True, ms=1, n_rows=1)
        assert len(svc._history) == MAX_HISTORY

    @patch("backend.modules.bd_clone.service._get_driver")
    def test_ejecutar_sql_select(self, mock_get):
        mock_drv = MagicMock()
        mock_drv.execute_query.return_value = [{"CODIGO":"45871","NOMBRE":"T"}]
        mock_drv.disconnect = MagicMock()
        mock_get.return_value = mock_drv
        from backend.modules.bd_clone.service import BDCloneService
        r = BDCloneService().ejecutar_sql("SELECT FIRST 1 * FROM PROYECTOS")
        assert r["ok"] is True and r["n_filas"] == 1

    @patch("backend.modules.bd_clone.service._get_driver")
    def test_probar_conexion_ok(self, mock_get):
        mock_drv = MagicMock()
        mock_drv.execute_query.return_value = [{"N": 437}]
        mock_drv.disconnect = MagicMock()
        mock_get.return_value = mock_drv
        from backend.modules.bd_clone.service import BDCloneService
        r = BDCloneService().probar_conexion()
        assert r["ok"] is True and r["n_tablas"] == 437

    @patch("backend.modules.bd_clone.service._get_driver")
    def test_probar_conexion_error(self, mock_get):
        mock_get.side_effect = Exception("Timeout")
        from backend.modules.bd_clone.service import BDCloneService
        r = BDCloneService().probar_conexion()
        assert r["ok"] is False and "Timeout" in r["error"]


class TestImportaciones:
    """BLOQUE E — Importaciones, singletons y estructura"""

    def test_api_clone_queries_completo(self):
        from backend.modules.api_clone.queries import (
            CLASE_TABLA_MAP, RIESGO_OPERACION, CONFIRMACION_REQUERIDA,
            OPERACIONES_ESCRITURA_REAL, ALL_CLASES,
        )
        assert ALL_CLASES is not None

    def test_api_clone_service_importa(self):
        from backend.modules.api_clone.service import ApiCloneService, get_service
        assert callable(get_service)

    def test_api_clone_router_importa(self):
        from backend.modules.api_clone.router import router
        assert router is not None

    def test_bd_clone_service_importa(self):
        from backend.modules.bd_clone.service import BDCloneService, get_service
        assert callable(get_service)

    def test_bd_clone_router_importa(self):
        from backend.modules.bd_clone.router import router
        assert router is not None

    def test_singleton_api_clone(self):
        from backend.modules.api_clone.service import get_service
        assert get_service() is get_service()

    def test_singleton_bd_clone(self):
        from backend.modules.bd_clone.service import get_service
        assert get_service() is get_service()

    def test_api_clone_router_endpoints_escritura(self):
        import inspect
        from backend.modules.api_clone import router as m
        src = inspect.getsource(m)
        for ep in ["/new","/edit","/write","/cancel","/imputa",
                   "/escritura/activar-paso1","/escritura/activar-paso2",
                   "/escritura/desactivar","/escritura/estado"]:
            assert ep in src, f"Endpoint '{ep}' no en router"

    def test_api_clone_router_endpoints_lectura(self):
        import inspect
        from backend.modules.api_clone import router as m
        src = inspect.getsource(m)
        for ep in ["/browse","/read","/permiso","/info","/discover-all","/catalogue"]:
            assert ep in src, f"Endpoint '{ep}' no en router"

    def test_bd_clone_router_endpoints(self):
        import inspect
        from backend.modules.bd_clone import router as m
        src = inspect.getsource(m)
        for ep in ["/status","/probar-conexion","/catalogo","/ejecutar-sql","/historial"]:
            assert ep in src, f"Endpoint '{ep}' no en bd_clone router"
