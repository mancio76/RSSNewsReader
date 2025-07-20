CREATE TABLE sources (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	base_url VARCHAR(255) NOT NULL, 
	rss_url VARCHAR(255), 
	description TEXT, 
	scraping_config JSON, 
	update_frequency INTEGER, 
	last_scraped DATETIME, 
	next_scrape DATETIME, 
	rate_limit_delay INTEGER, 
	is_active BOOLEAN, 
	error_count INTEGER, 
	last_error TEXT, 
	created_date DATETIME, 
	updated_date DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE categories (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(255), 
	parent_id INTEGER, 
	color VARCHAR(7), 
	icon VARCHAR(50), 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(parent_id) REFERENCES categories (id)
);
CREATE TABLE articles (
	id INTEGER NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	content TEXT, 
	summary TEXT, 
	url VARCHAR(1000) NOT NULL, 
	author VARCHAR(200), 
	source_id INTEGER NOT NULL, 
	published_date DATETIME, 
	scraped_date DATETIME, 
	updated_date DATETIME, 
	content_hash VARCHAR(64), 
	url_hash VARCHAR(64), 
	word_count INTEGER, 
	language VARCHAR(10), 
	sentiment_score FLOAT, 
	is_duplicate BOOLEAN, 
	is_processed BOOLEAN, 
	PRIMARY KEY (id), 
	UNIQUE (url), 
	FOREIGN KEY(source_id) REFERENCES sources (id)
);
CREATE INDEX ix_articles_published_source ON articles (published_date, source_id);
CREATE INDEX ix_articles_content_hash ON articles (content_hash);
CREATE INDEX ix_articles_url_hash ON articles (url_hash);
CREATE INDEX ix_articles_scraped_date ON articles (scraped_date);
CREATE TABLE article_metadata (
	id INTEGER NOT NULL, 
	article_id INTEGER NOT NULL, 
	"key" VARCHAR(50) NOT NULL, 
	value TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(article_id) REFERENCES articles (id)
);
CREATE TABLE article_versions (
	id INTEGER NOT NULL, 
	article_id INTEGER NOT NULL, 
	title VARCHAR(500), 
	content TEXT, 
	summary TEXT, 
	version_number INTEGER, 
	change_type VARCHAR(20), 
	change_description TEXT, 
	created_date DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(article_id) REFERENCES articles (id)
);
CREATE TABLE article_tags (
	id INTEGER NOT NULL, 
	article_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, 
	confidence FLOAT, 
	source VARCHAR(20), 
	created_date DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(article_id) REFERENCES articles (id), 
	FOREIGN KEY(tag_id) REFERENCES tags (id)
);
CREATE TABLE tags (id INTEGER NOT NULL, name VARCHAR (100) NOT NULL, normalized_name VARCHAR (100), category_id INTEGER, frequency INTEGER, tag_type VARCHAR (20), created_date DATETIME, PRIMARY KEY (id), UNIQUE (name), FOREIGN KEY (category_id) REFERENCES categories (id));
CREATE INDEX ix_tags_normalized_name ON tags (normalized_name);
