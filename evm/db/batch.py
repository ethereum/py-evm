from evm.db.journal import (
    JournalDB,
)


class BatchDB(JournalDB):
    """
    BatchDB builds on top of evm.db.journal.JournalDB and adds batch capability.
    All operations performed within a context manager is saved to a temporary database.
    This is committed to the final database if execution of everything within
    the context manager is successful. Otherwise results are rolledback to the initial state
    before execution.
    """
    def __init__(self, db):
        JournalDB.__init__(self, db)
        self.db_class = db
        self.db = db()
        self.tmp_db = db()

    def commit(self):
        # Commit the values in temp_db to our db
        # And reset the tmp_db
        self.db = self.db_class(self.tmp_db)
        self.tmp_db = self.db_class()
        self.wrapped_db = self.db_class(self.db)

    def rollback(self, exception):
        # Clear tmp_db and raise exception
        self.tmp_db = self.db_class()
        self.wrapped_db = self.db_class(self.db)
        raise exception

    def __enter__(self):
        self.wrapped_db = self.db_class(self.tmp_db)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if exception_type:
            self.rollback(exception_type)
        else:
            self.commit()
