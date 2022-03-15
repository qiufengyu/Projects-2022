create table "user"
(
    username varchar(64),
    nickname varchar(64),
    password varchar(64)
);

alter table "user"
    owner to demo;

grant delete, insert, references, select, trigger, truncate, update on "user" to postgres;