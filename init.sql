CREATE TABLE chat_tab (
	video_id varchar(255),
	chat_id varchar(255) NOT NULL PRIMARY KEY,
	text varchar(255),
	timestamp varchar(255),
	author_name varchar(255),
	author_id varchar(255)
);

CREATE TABLE stream_tab (
	id varchar(255) NOT NULL PRIMARY KEY,
	title varchar(255),
	topic_id varchar(255),
	channel_id varchar(255),
	channel_name varchar(255)
);
