CREATE TABLE d_server (
id varchar(36) primary key not null,
name varchar(40) not null,
ip varchar(39) not null,
port integer not null,
birth datetime,
keep_alive integer,
available boolean,
granules text,
route text,
alt_route text
);

CREATE TABLE d_action_template
(id varchar(36) primary key not null,
name text not null,
version integer not null,
action_type integer not null,
code text,
parameters text,
system_kwargs text,
expected_output text,
expected_rc integer);

CREATE UNIQUE INDEX d_action_template_ix1
on d_action_template (name, version);

create table l_catalog
(entity varchar(40) primary key not null,
data_mark text not null);

CREATE TABLE l_dimension
(id varchar(36) primary key not null,
name text,
priv blob,
pub blob,
created datetime);

CREATE UNIQUE INDEX l_dimension_ix1
on d_action_template (name);

CREATE TABLE d_step (
id varchar(36) primary key not null,
undo boolean not null,
stop_on_error boolean not null,
action_template varchar(36) not null,
step_expected_output text,
step_expected_rc integer,
step_parameters text,
step_system_kwargs text,
orchestration varchar(36) not null,
CONSTRAINT fk_action_template FOREIGN KEY(action_template) REFERENCES d_action_template(id)
);

CREATE TABLE d_orchestration (
id varchar(36) primary key not null,
name text not null,
version integer not null,
description text
);

CREATE UNIQUE INDEX d_orchestration_ix1
on d_orchestration (name, version);

CREATE TABLE d_orchestration_step (
orchestration varchar(36) not null,
step varchar(36) not null,
CONSTRAINT fk_orchestration FOREIGN KEY(orchestration) REFERENCES d_orchestration(id),
CONSTRAINT fk_step FOREIGN KEY(step) REFERENCES d_step(id)
);

CREATE TABLE d_step_step (
step varchar(36) not null,
child_step varchar(36) not null,
CONSTRAINT fk_step FOREIGN KEY(step) REFERENCES d_step(id),
CONSTRAINT fk_child_step FOREIGN KEY(child_step) REFERENCES d_step(id)
);

CREATE TABLE l_execution (
id varchar(36) primary key not null,
orchestration varchar(36) not null,
step varchar(36) not null,
server varchar(36) not null,
params text,
stdout text,
stderr text,
rc integer,
start_time datetime,
end_time datetime,
CONSTRAINT fk_orchestration FOREIGN KEY(orchestration) REFERENCES d_orchestration(id),
CONSTRAINT fk_step FOREIGN KEY(step) REFERENCES d_step(id),
CONSTRAINT fk_server FOREIGN KEY(server) REFERENCES d_server(id)
);

CREATE TABLE l_log (
id varchar(36) primary key not null,
file varchar(255) not null,
server varchar(36),
dest_folder text not null,
dest_name varchar(255) not null,
time integer not null,
CONSTRAINT fk_server FOREIGN KEY(server) REFERENCES d_server(id)
);

CREATE TABLE d_user (
id varchar(36) primary key not null,
username varchar(255) not null,
password varchar(255) not null,
created_on datetime
);

CREATE UNIQUE INDEX d_user_ix1
on d_user (username);