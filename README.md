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

"dimensigon-node1": "ba81a3a0-3a76-47cc-b1bd-4e62e95f0586"
"dimensigon-node2": "a47b2dd4-7961-417c-a4e3-293cc97ac056"
"dimensigon-node3": "d3a98a9f-31d4-43c7-8316-2a8fb2f338e1"
        
 