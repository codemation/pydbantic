import setuptools

BASE_REQUIREMENTS = [
    'SQLAlchemy==1.4.28',
    'databases==0.5.3', 
    'aioredis==2.0.0', 
    'pydantic==1.8.2',
]
MYSQL_REQUIREMENTS = [
    'aiomysql==0.0.21',
    'cryptography==3.4.8',
    'mysqlclient==2.0.3',
    'PyMySQL==0.9.3',
]
POSTGRES_REQUIREMENTS = [
    'asyncpg==0.24.0',
    'psycopg2==2.9.1',
]
LITE_REQUIREMENTS = [
    'aiosqlite==0.17.0',
]

with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
     name='pydbantic',  
     version='NEXT_VERSION',
     packages=setuptools.find_packages(include=['pydbantic'], exclude=['build']),
     author="Joshua Jamison",
     author_email="joshjamison1@gmail.com",
     description="'db' within pydantic - A single model for shaping, creating, accessing, storing data within a Database",
     long_description=long_description,
   long_description_content_type="text/markdown",
     url="https://github.com/codemation/pydbantic",
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
     ],
     python_requires='>=3.7, <4',   
     install_requires=BASE_REQUIREMENTS,
     extras_require={
         'all': BASE_REQUIREMENTS + POSTGRES_REQUIREMENTS + MYSQL_REQUIREMENTS + LITE_REQUIREMENTS,
         'postgres': POSTGRES_REQUIREMENTS,
         'mysql': MYSQL_REQUIREMENTS,
         'sqlite': LITE_REQUIREMENTS
     }
 )