from app.database.connection import check_db_connection, engine


def test_db_connection_function():
    # Calling check_db_connection should safely return a dict with connected key
    result = check_db_connection()
    assert isinstance(result, dict)
    assert "connected" in result
