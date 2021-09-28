import sqlalchemy

DEFAULT_TRANSLATIONS = {
    "MYSQL": {
        str: {
            "column_type": sqlalchemy.String,
            "args": [60],
            "kwargs": {}
        },
        int: {
            "column_type": sqlalchemy.Integer,
            "args": [],
            "kwargs": {}
        },
        float: {
            "column_type": sqlalchemy.Float,
            "args": [],
            "kwargs": {}
        },
        bool: {
            "column_type": sqlalchemy.Boolean,
            "args": [],
            "kwargs": {}
        },
        dict: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        list: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        tuple: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        "default": {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        }
    },
    "POSTGRES": {
        int: {
            "column_type": sqlalchemy.Integer,
            "args": [],
            "kwargs": {}
        },
        float: {
            "column_type": sqlalchemy.Float,
            "args": [],
            "kwargs": {}
        },
        bool: {
            "column_type": sqlalchemy.Boolean,
            "args": [],
            "kwargs": {}
        },
        dict: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        list: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        tuple: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        "default": {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },

        str: {
            "column_type": sqlalchemy.String,
            "args": [],
            "kwargs": {}
        },
    },
    "SQLITE": {
        str: {
            "column_type": sqlalchemy.String,
            "args": [60],
            "kwargs": {}
        },
        int: {
            "column_type": sqlalchemy.Integer,
            "args": [],
            "kwargs": {}
        },
        float: {
            "column_type": sqlalchemy.Float,
            "args": [],
            "kwargs": {}
        },
        bool: {
            "column_type": sqlalchemy.Boolean,
            "args": [],
            "kwargs": {}
        },
        dict: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        list: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        tuple: {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        },
        "default": {
            "column_type": sqlalchemy.LargeBinary,
            "args": [],
            "kwargs": {}
        }
    },
}