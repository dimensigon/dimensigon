# dimensigon
Dimensigon (Core, AutoUpgrader, DShell)


#### Deletion of all desktop.ini files
```gitignore
DEL /A:H /S /Q desktop.ini
```

####Launch Coverage report for tests
````gitignore
coverage run --source=dm -m unittest
coverage report -m
````