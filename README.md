ong_mole
========

# Description
Scripts to download mole price data from sets defined in mole.

To log in, opens a Chrome browser window and waits to log in, getting credentials from it.

Uses cache to avoid asking for login data unnecessarily, as if stored credentials did not expire, then the program 
reuses them

# Requisites
Create a file in homedir named `.config/ongpi/ong_mole.yaml` with the following content (adapted to your case):

````yaml
log: {}
ong_mole:
  server: put your server name here (without trailing /), such as https://www.mole.com
ong_mole_test:
  test_set: if you want to run tests, put here a valid mole set name
````

 # Sample code
```python
from ong_mole.mole import Mole
mole = Mole()
set_name = "put a sample set name here"
df = mole.download_df(set_name)
created_file = mole.download_file(set_name)
created_file2 = mole.download_file(set_name, path="directory for downloaded file")
```