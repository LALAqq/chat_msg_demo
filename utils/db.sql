create message_center if not exists message_center;
use message_center;

create table if not exists user_info(
    `user_id` varchar(100) not NULL,
    `passwd` varchar(100) not NULL,
    PRIMARY KEY (`user_id`)
) DEFAULT CHARSET = utf8;

create table if not exists user_contacts(
    `user_id`           varchar(100) not NULL,
    `contacts_id`       varchar(100) not NULL,
    `unread_msg_cnt`   int DEFAULT 0,
    `last_read_time` TIMESTAMP,
    PRIMARY KEY (`user_id`, `contacts_id`),
    FOREIGN KEY (`user_id`) REFERENCES user_info(`user_id`),
    FOREIGN KEY (`contacts_id`) REFERENCES user_info(`user_id`)
) DEFAULT CHARSET = utf8;

create table if not exists msg_record(
    `msg_id`        varchar(128) not NULL,
    `sender_id`     varchar(100) not NULL,
    `receiver_id`   varchar(100) not NULL,
    `send_time`     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `msg_content`   varchar(1000) not NULL,
    `status`        int DEFAULT 0,
    PRIMARY KEY (`msg_id`),
    KEY(`sender_id`, `receiver_id`),
    FOREIGN KEY (`sender_id`) REFERENCES user_info(`user_id`),
    FOREIGN KEY (`receiver_id`) REFERENCES user_info(`user_id`)
) DEFAULT CHARSET = utf8;
