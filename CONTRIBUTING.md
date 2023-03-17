## How to Contribute

### Developing Guidelines - Pull Request
Pull requests are welcomed along with the following:
- PR documenting what is changed, why it is changed / needed
- Pre-commit formatting, otherwise LINT will fail
- New / Update to tests for new functionality


#### Requirements
Known Linux Requirements
```
sudo apt-get install libmysqlclient-dev & libpq-dev
```

#### Create Virtual Environment

```bash
virtualenv -p python3 py-env
```

Activate
```bash
source py-env/bin/activate
```

#### Install Depedencies

```bash
(py-env) $ pip install -r requirements-test.txt
```

#### Setup Pre Commit
```bash
(py-env) $ pre-commit install
```

#### Run Tests
Tests can be started via vscode debugger, or using make

(py-env) $ make test

(py-env) $ make test-migrations

