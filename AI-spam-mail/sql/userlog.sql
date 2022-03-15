-- auto-generated definition
create table userlog
(
    id      int auto_increment
        primary key,
    `from`  varchar(63)   not null,
    `to`    varchar(63)   not null,
    subject varchar(255)  null,
    content blob          null,
    time    timestamp     null,
    status  int default 0 null
);
