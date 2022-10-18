drop table if exists performance_logs;
create table performance_logs
(
	log_id serial primary key,
	pid integer,
	timestamp timestamp,
	start_id integer,
	end_id integer,
	module text,
	name text,
	duration real
);

drop table if exists files;
create table files
(
	file_id integer primary key,
	folder_id integer,
	name text,
    rel_path text,
	ext text,
	line_count integer,
	char_count integer
);

drop table if exists folders;
create table folders
(
	folder_id integer primary key,
	parent_id integer,
	abs_path text,
	rel_path text,
	name text
);

drop table if exists comments;
create table comments
(
	comment_id serial primary key,
	file_id integer, 
	comment text, 
	line_start integer,
	line_end integer
)