from app.config import Settings


def test_database_url_gets_the_psycopg_driver():
    expected = "postgresql+psycopg://u:p@host/db"
    assert Settings(database_url="postgres://u:p@host/db").database_url == expected
    assert Settings(database_url="postgresql://u:p@host/db").database_url == expected
    assert Settings(database_url=expected).database_url == expected  # already correct: unchanged