-- ============================================================
-- GEO Integration Platform 完整数据库表结构（MySQL 8.x / 5.7+）
-- 与 backend/app/models.py 一一对应（31 张表）
-- 用法：mysql -u geo -p geo_platform < sql/schema.sql
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS geo_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE geo_platform;

-- ============ 用户与账号 ============

CREATE TABLE IF NOT EXISTS `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `email` VARCHAR(128) NOT NULL DEFAULT '',
  `phone` VARCHAR(20) NOT NULL DEFAULT '',
  `password_hash` VARCHAR(256) NOT NULL,
  `is_vip` TINYINT(1) NOT NULL DEFAULT 0,
  `vip_expires_at` DATETIME NULL,
  `balance` DOUBLE NOT NULL DEFAULT 0,
  `local_balance` DOUBLE NOT NULL DEFAULT 0,
  `geo_token` VARCHAR(80) NOT NULL DEFAULT '',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `is_admin` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NULL,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_username` (`username`),
  KEY `ix_users_geo_token` (`geo_token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `company_profiles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `company_name` VARCHAR(128) NOT NULL DEFAULT '',
  `industry` VARCHAR(64) NOT NULL DEFAULT '',
  `website` VARCHAR(256) NOT NULL DEFAULT '',
  `contact` VARCHAR(64) NOT NULL DEFAULT '',
  `logo` VARCHAR(512) NOT NULL DEFAULT '',
  `description` TEXT,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_company_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `brands` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `brand_type` VARCHAR(16) NOT NULL DEFAULT 'main',
  `description` TEXT,
  `main_brand_id` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_brands_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `brand_documents` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `brand_id` INT NOT NULL,
  `filename` VARCHAR(256) NOT NULL DEFAULT '',
  `doc_type` VARCHAR(32) NOT NULL DEFAULT 'text',
  `content` LONGTEXT,
  `status` VARCHAR(16) NOT NULL DEFAULT 'ready',
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_brand_documents_brand_id` (`brand_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `keyword_settings` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NULL,
  `brand_id` INT NULL,
  `settings` LONGTEXT,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_keyword_settings_user_id` (`user_id`),
  KEY `ix_keyword_settings_brand_id` (`brand_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============ 关键词与 GEO 评估 ============

CREATE TABLE IF NOT EXISTS `keywords` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `brand_id` INT NULL,
  `keyword` VARCHAR(256) NOT NULL,
  `category` VARCHAR(64) NOT NULL DEFAULT '',
  `priority` INT NOT NULL DEFAULT 0,
  `status` VARCHAR(16) NOT NULL DEFAULT 'pending',
  `geo_score` DOUBLE NOT NULL DEFAULT 0,
  `last_check_id` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_keywords_user_id` (`user_id`),
  KEY `ix_keywords_brand_id` (`brand_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `keyword_tags` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `name` VARCHAR(64) NOT NULL,
  `color` VARCHAR(16) NOT NULL DEFAULT '#409EFF',
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tag_user_name` (`user_id`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `keyword_tag_maps` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `keyword_id` INT NOT NULL,
  `tag_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_kw_tag` (`keyword_id`,`tag_id`),
  KEY `ix_keyword_tag_maps_tag_id` (`tag_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `check_tasks` (
  `id` VARCHAR(64) NOT NULL,
  `user_id` INT NOT NULL,
  `keyword_id` INT NULL,
  `batch_no` VARCHAR(64) NOT NULL DEFAULT '',
  `engines` LONGTEXT,
  `status` VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  `progress` INT NOT NULL DEFAULT 0,
  `error` LONGTEXT,
  `scheduler_task_id` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_check_tasks_user_id` (`user_id`),
  KEY `ix_check_tasks_keyword_id` (`keyword_id`),
  KEY `ix_check_tasks_batch_no` (`batch_no`),
  KEY `ix_check_tasks_scheduler_task_id` (`scheduler_task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `check_results` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `task_id` VARCHAR(64) NOT NULL,
  `keyword_id` INT NOT NULL,
  `engine` VARCHAR(32) NOT NULL,
  `cited` TINYINT(1) NOT NULL DEFAULT 0,
  `rank` INT NOT NULL DEFAULT 0,
  `mention_rate` DOUBLE NOT NULL DEFAULT 0,
  `sentiment` VARCHAR(16) NOT NULL DEFAULT 'neutral',
  `geo_score` DOUBLE NOT NULL DEFAULT 0,
  `answer` LONGTEXT,
  `sources` LONGTEXT,
  `checked_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_check_results_task_id` (`task_id`),
  KEY `ix_check_results_keyword_id` (`keyword_id`),
  KEY `ix_check_results_engine` (`engine`),
  KEY `ix_check_results_kw_engine` (`keyword_id`,`engine`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `compliance_reports` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `keyword_id` INT NULL,
  `content_id` INT NULL,
  `score` DOUBLE NOT NULL DEFAULT 0,
  `risk_level` VARCHAR(16) NOT NULL DEFAULT 'low',
  `summary` LONGTEXT,
  `locked` TINYINT(1) NOT NULL DEFAULT 1,
  `scheduler_task_id` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_compliance_reports_user_id` (`user_id`),
  KEY `ix_compliance_reports_keyword_id` (`keyword_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `compliance_findings` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `report_id` INT NOT NULL,
  `rule_code` VARCHAR(32) NOT NULL DEFAULT '',
  `category` VARCHAR(32) NOT NULL DEFAULT '',
  `severity` VARCHAR(16) NOT NULL DEFAULT 'low',
  `fragment` LONGTEXT,
  `suggestion` LONGTEXT,
  PRIMARY KEY (`id`),
  KEY `ix_compliance_findings_report_id` (`report_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `engines` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `key` VARCHAR(32) NOT NULL,
  `name` VARCHAR(64) NOT NULL DEFAULT '',
  `vendor` VARCHAR(64) NOT NULL DEFAULT '',
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `weight` DOUBLE NOT NULL DEFAULT 1,
  `order` INT NOT NULL DEFAULT 0,
  `config` LONGTEXT,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_engines_key` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `ai_search_results` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `keyword_id` INT NOT NULL,
  `engine` VARCHAR(32) NOT NULL,
  `question` LONGTEXT,
  `answer` LONGTEXT,
  `sources` LONGTEXT,
  `rank` INT NOT NULL DEFAULT 0,
  `cited` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_ai_search_results_user_id` (`user_id`),
  KEY `ix_ai_search_results_keyword_id` (`keyword_id`),
  KEY `ix_ai_search_results_engine` (`engine`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============ 知识库 ============

CREATE TABLE IF NOT EXISTS `knowledge_bases` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `brand_id` INT NOT NULL,
  `title` VARCHAR(256) NOT NULL DEFAULT '',
  `content` LONGTEXT,
  `status` VARCHAR(16) NOT NULL DEFAULT 'draft',
  `version` INT NOT NULL DEFAULT 1,
  `published_at` DATETIME NULL,
  `created_at` DATETIME NULL,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_knowledge_bases_user_id` (`user_id`),
  KEY `ix_knowledge_bases_brand_id` (`brand_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `kb_versions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `kb_id` INT NOT NULL,
  `version_no` INT NOT NULL DEFAULT 1,
  `content` LONGTEXT,
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_kb_versions_kb_id` (`kb_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `kb_tasks` (
  `id` VARCHAR(64) NOT NULL,
  `user_id` INT NOT NULL,
  `brand_id` INT NOT NULL,
  `task_type` VARCHAR(32) NOT NULL DEFAULT 'build',
  `status` VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  `progress` INT NOT NULL DEFAULT 0,
  `result` LONGTEXT,
  `error` LONGTEXT,
  `scheduler_task_id` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_kb_tasks_user_id` (`user_id`),
  KEY `ix_kb_tasks_brand_id` (`brand_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============ 内容与发布 ============

CREATE TABLE IF NOT EXISTS `contents` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `brand_id` INT NULL,
  `title` VARCHAR(256) NOT NULL DEFAULT '',
  `keywords` LONGTEXT,
  `category` VARCHAR(64) NOT NULL DEFAULT '',
  `length` INT NOT NULL DEFAULT 1200,
  `summary` LONGTEXT,
  `body` LONGTEXT,
  `engine_key` VARCHAR(32) NOT NULL DEFAULT 'deepseek',
  `special_requirements` LONGTEXT,
  `status` VARCHAR(16) NOT NULL DEFAULT 'generating',
  `cover_url` VARCHAR(512) NOT NULL DEFAULT '',
  `images` LONGTEXT,
  `cost` DOUBLE NOT NULL DEFAULT 0,
  `created_at` DATETIME NULL,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_contents_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `media_platforms` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `key` VARCHAR(32) NOT NULL,
  `name` VARCHAR(64) NOT NULL DEFAULT '',
  `icon` VARCHAR(256) NOT NULL DEFAULT '',
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `supports_images` TINYINT(1) NOT NULL DEFAULT 1,
  `api_type` VARCHAR(32) NOT NULL DEFAULT 'extension',
  `order` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_media_platforms_key` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `media_channels` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `platform_key` VARCHAR(32) NOT NULL DEFAULT '',
  `channel_name` VARCHAR(128) NOT NULL DEFAULT '',
  `category` VARCHAR(32) NOT NULL DEFAULT '',
  `account` VARCHAR(128) NOT NULL DEFAULT '',
  `followers` INT NOT NULL DEFAULT 0,
  `price` DOUBLE NOT NULL DEFAULT 0,
  `status` VARCHAR(16) NOT NULL DEFAULT 'active',
  `channel_url` VARCHAR(512) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`),
  KEY `ix_media_channels_platform_key` (`platform_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `publish_tasks` (
  `id` VARCHAR(64) NOT NULL,
  `user_id` INT NOT NULL,
  `content_id` INT NOT NULL,
  `platform_key` VARCHAR(32) NOT NULL,
  `account_id` INT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'pending',
  `cost` DOUBLE NOT NULL DEFAULT 0,
  `publish_url` VARCHAR(512) NOT NULL DEFAULT '',
  `error` LONGTEXT,
  `scheduled_at` DATETIME NULL,
  `scheduler_task_id` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_publish_tasks_user_id` (`user_id`),
  KEY `ix_publish_tasks_content_id` (`content_id`),
  KEY `ix_publish_tasks_platform_key` (`platform_key`),
  KEY `ix_publish_tasks_user_status` (`user_id`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `social_accounts` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `platform_key` VARCHAR(32) NOT NULL,
  `account_name` VARCHAR(128) NOT NULL DEFAULT '',
  `avatar` VARCHAR(512) NOT NULL DEFAULT '',
  `cookie_status` VARCHAR(16) NOT NULL DEFAULT 'valid',
  `is_auto_mode` TINYINT(1) NOT NULL DEFAULT 0,
  `last_heartbeat` DATETIME NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `ix_social_accounts_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `social_publish_tasks` (
  `id` VARCHAR(64) NOT NULL,
  `user_id` INT NOT NULL,
  `content_id` INT NOT NULL,
  `platform_key` VARCHAR(32) NOT NULL,
  `account_id` INT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'pending',
  `result_url` VARCHAR(512) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_social_publish_tasks_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============ 计费与订单 ============

CREATE TABLE IF NOT EXISTS `retail_price_config` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `action_type` VARCHAR(32) NOT NULL,
  `price_mode` VARCHAR(16) NOT NULL DEFAULT 'fixed',
  `price_value` DOUBLE NOT NULL DEFAULT 0,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_retail_action` (`action_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `local_consumption_records` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `record_id` VARCHAR(32) NOT NULL,
  `user_id` INT NOT NULL,
  `action_type` VARCHAR(32) NOT NULL DEFAULT '',
  `record_type` VARCHAR(32) NOT NULL DEFAULT 'consume',
  `amount` DOUBLE NOT NULL DEFAULT 0,
  `balance_after` DOUBLE NOT NULL DEFAULT 0,
  `status` VARCHAR(16) NOT NULL DEFAULT 'success',
  `description` VARCHAR(256) NOT NULL DEFAULT '',
  `ref_id` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_record_id` (`record_id`),
  KEY `ix_local_consumption_records_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `orders` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `order_no` VARCHAR(64) NOT NULL,
  `user_id` INT NOT NULL,
  `plan_type` VARCHAR(32) NOT NULL DEFAULT 'monthly',
  `payment_method` VARCHAR(32) NOT NULL DEFAULT 'alipay',
  `amount` DOUBLE NOT NULL DEFAULT 0,
  `status` VARCHAR(16) NOT NULL DEFAULT 'pending',
  `credits` DOUBLE NOT NULL DEFAULT 0,
  `paid_at` DATETIME NULL,
  `raw` LONGTEXT,
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_orders_order_no` (`order_no`),
  KEY `ix_orders_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============ 工单 ============

CREATE TABLE IF NOT EXISTS `tickets` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `ticket_no` VARCHAR(32) NOT NULL DEFAULT '',
  `title` VARCHAR(256) NOT NULL DEFAULT '',
  `content` LONGTEXT,
  `category` VARCHAR(32) NOT NULL DEFAULT 'other',
  `priority` VARCHAR(16) NOT NULL DEFAULT 'normal',
  `status` VARCHAR(16) NOT NULL DEFAULT 'open',
  `ai_analysis` LONGTEXT,
  `created_at` DATETIME NULL,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tickets_ticket_no` (`ticket_no`),
  KEY `ix_tickets_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `ticket_responses` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `ticket_id` INT NOT NULL,
  `responder_id` INT NULL,
  `responder_type` VARCHAR(16) NOT NULL DEFAULT 'admin',
  `content` LONGTEXT,
  `created_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_ticket_responses_ticket_id` (`ticket_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============ CPU 调度器 ============

CREATE TABLE IF NOT EXISTS `scheduler_tasks` (
  `id` VARCHAR(64) NOT NULL,
  `task_type` VARCHAR(32) NOT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  `priority` INT NOT NULL DEFAULT 5,
  `cpu_cores` INT NOT NULL DEFAULT 1,
  `timeout_s` INT NOT NULL DEFAULT 600,
  `max_retry` INT NOT NULL DEFAULT 2,
  `attempts` INT NOT NULL DEFAULT 0,
  `payload` LONGTEXT,
  `result` LONGTEXT,
  `progress` INT NOT NULL DEFAULT 0,
  `error` LONGTEXT,
  `tenant` VARCHAR(64) NOT NULL DEFAULT '',
  `executor` VARCHAR(16) NOT NULL DEFAULT 'local',
  `slurm_job_id` VARCHAR(32) NOT NULL DEFAULT '',
  `created_at` DATETIME NULL,
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_scheduler_tasks_task_type` (`task_type`),
  KEY `ix_scheduler_tasks_status` (`status`),
  KEY `ix_scheduler_tasks_tenant` (`tenant`),
  KEY `ix_scheduler_tasks_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `task_usage` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `task_id` VARCHAR(64) NULL,
  `tenant` VARCHAR(64) NOT NULL DEFAULT '',
  `task_type` VARCHAR(32) NOT NULL DEFAULT '',
  `cores` INT NOT NULL DEFAULT 1,
  `cpu_seconds` DOUBLE NOT NULL DEFAULT 0,
  `queued_s` DOUBLE NOT NULL DEFAULT 0,
  `run_s` DOUBLE NOT NULL DEFAULT 0,
  `finished_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_task_usage_task_id` (`task_id`),
  KEY `ix_task_usage_tenant` (`tenant`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `compute_nodes` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `hostname` VARCHAR(128) NOT NULL DEFAULT '',
  `partition` VARCHAR(64) NOT NULL DEFAULT 'local',
  `state` VARCHAR(32) NOT NULL DEFAULT 'idle',
  `cores_total` INT NOT NULL DEFAULT 0,
  `cores_used` INT NOT NULL DEFAULT 0,
  `mem_gb` INT NOT NULL DEFAULT 0,
  `updated_at` DATETIME NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;

-- 默认零售价（协议 §4）
INSERT IGNORE INTO `retail_price_config` (`action_type`, `price_mode`, `price_value`) VALUES
  ('KEYWORD_CHECK', 'fixed', 10.0),
  ('CONTENT_GENERATE', 'multiplier', 1.0),
  ('CONTENT_PUBLISH', 'multiplier', 1.0),
  ('BRAND_KNOWLEDGE', 'fixed', 10.0),
  ('COMPLIANCE_UNLOCK', 'multiplier', 1.0);
