from unittest.mock import MagicMock
import pytest
from backend.modules.api_clone.utilidades.project_lookup import search


def test_search_is_parameterized_and_paged():
    drv = MagicMock()
    drv.execute_query.side_effect = [[{"N": 31}], [{"CODIGO": "A", "NOMBRE": "Obra", "FINOBRA": "T"}]]
    result = search(lambda: drv, "O'Brien", 15, 15)
    assert result["total"] == 31 and result["hay_mas"]
    assert result["offset"] == 15
    assert result["valores"][0]["estado"] == "Finalizado"
    sql, params = drv.execute_query.call_args.args
    assert "FIRST 15 SKIP 15" in sql
    assert "O'Brien" not in sql
    assert params == ("O'Brien", "O'Brien")
    drv.disconnect.assert_called_once()


def test_last_page():
    drv = MagicMock()
    drv.execute_query.side_effect = [[{"N": 16}], [{"CODIGO": "A", "NOMBRE": "Obra", "FINOBRA": "F"}]]
    result = search(lambda: drv, "", 15, 15)
    assert not result["hay_mas"]


def test_database_failure_closes_connection():
    drv = MagicMock()
    drv.execute_query.side_effect = RuntimeError("DB")
    with pytest.raises(RuntimeError):
        search(lambda: drv)
    drv.disconnect.assert_called_once()
