import setuptools
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
     install_requires=[
         'SQLAlchemy==1.3.24', 
         'databases==0.4.3', 
         'aioredis==2.0.0', 
         'pydantic==1.8.2',
         'asyncpg==0.24.0',
         'aiosqlite==0.17.0'
    ],
 )