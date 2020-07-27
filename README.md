# dimensigon
Dimensigon (Core, AutoUpgrader, DShell)

####Launch Coverage report for tests
````gitignore
coverage run --source=dm -m unittest
coverage report -m
````


Query to check routes from database
```sqlite
select s1.name "destination", 
       r.proxy_server_id,
       r.cost,
       s2.name "server_gate", 
       g.dns, 
       g.ip, 
       g.port 
  from l_route r 
 inner join d_gate g on r.gate_id = g.id 
 inner join d_server s1 on r.destination_id = s1.id 
 inner join d_server s2 on g.server_id = s2.id;
```

Query server and gates
```sqlite
select s.name, g.dns, g.ip, g.port 
  from d_server s 
 inner join d_gate g on s.id = g.server_id 
 order by s.name;
```

# Install locally
```shell script
pip wheel --wheel-dir=files dimensigon
pip install --no-index --find-links=./files dimensigon
```
