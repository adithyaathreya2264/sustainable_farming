-- Baseline schema: the database as of Alembic revision e1f2a3b4c5d6
-- (cumulative result of `alembic upgrade head`, captured via SHOW CREATE TABLE).

CREATE TABLE `users` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone_number` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `language_pref` varchar(8) COLLATE utf8mb4_unicode_ci NOT NULL,
  `default_unit` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `total_area_hectares` decimal(12,4) NOT NULL,
  `irrigation_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `state` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `district` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `onboarding_complete` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `unique_id` varchar(4) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `phone_number` (`phone_number`),
  UNIQUE KEY `uq_users_unique_id` (`unique_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `locations` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `state` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `district` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_locations_state_district` (`state`,`district`),
  KEY `ix_locations_state` (`state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `govt_schemes` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `scheme_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `authority` varchar(160) COLLATE utf8mb4_unicode_ci NOT NULL,
  `eligibility_criteria` json NOT NULL,
  `benefit_description` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `application_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `crops` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `crop_varieties` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `crop_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_crop_varieties_crop_id` (`crop_id`),
  CONSTRAINT `crop_varieties_ibfk_1` FOREIGN KEY (`crop_id`) REFERENCES `crops` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `agri_catalog` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` enum('seed','fertilizer','pesticide','herbicide','fungicide','biocontrol') COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(160) COLLATE utf8mb4_unicode_ci NOT NULL,
  `crop_applicability` json DEFAULT NULL,
  `unit_of_measure` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL,
  `typical_dosage_per_hectare` decimal(14,4) DEFAULT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `crop_growth_stages` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `crop_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stage_name` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stage_order` int NOT NULL,
  `typical_days_from_sowing_start` int NOT NULL,
  `typical_days_from_sowing_end` int NOT NULL,
  `confidence` enum('low','medium','verified') COLLATE utf8mb4_unicode_ci NOT NULL,
  `source` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_crop_growth_stages_crop_id` (`crop_id`),
  CONSTRAINT `crop_growth_stages_ibfk_1` FOREIGN KEY (`crop_id`) REFERENCES `crops` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `agronomic_rules` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rule_code` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `crop_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stage_name` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `condition_field` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `operator` varchar(8) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `threshold_value` decimal(14,4) DEFAULT NULL,
  `severity` enum('info','advisory','critical') COLLATE utf8mb4_unicode_ci NOT NULL,
  `recommendation_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `confidence` enum('low','medium','verified') COLLATE utf8mb4_unicode_ci NOT NULL,
  `source` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_agronomic_rules_crop_id` (`crop_id`),
  KEY `ix_agronomic_rules_rule_code` (`rule_code`),
  CONSTRAINT `agronomic_rules_ibfk_1` FOREIGN KEY (`crop_id`) REFERENCES `crops` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `fields` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `area_size_hectares` decimal(12,4) NOT NULL,
  `lat` decimal(10,7) NOT NULL,
  `long` decimal(10,7) NOT NULL,
  `boundary` json NOT NULL,
  `soil_type` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_fields_user_id` (`user_id`),
  CONSTRAINT `fields_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `plantings` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `field_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `crop_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `variety_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sowing_date` date NOT NULL,
  `status` enum('active','harvested') COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_plantings_field_id` (`field_id`),
  KEY `ix_plantings_crop_id` (`crop_id`),
  KEY `variety_id` (`variety_id`),
  CONSTRAINT `plantings_ibfk_1` FOREIGN KEY (`field_id`) REFERENCES `fields` (`id`),
  CONSTRAINT `plantings_ibfk_2` FOREIGN KEY (`crop_id`) REFERENCES `crops` (`id`),
  CONSTRAINT `plantings_ibfk_3` FOREIGN KEY (`variety_id`) REFERENCES `crop_varieties` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `interventions` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `planting_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` enum('chemical','irrigation','labor','harvest') COLLATE utf8mb4_unicode_ci NOT NULL,
  `product_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quantity_metric` decimal(14,4) DEFAULT NULL,
  `quantity_unit` varchar(24) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cost_in_inr` decimal(14,2) NOT NULL,
  `intervention_date` date NOT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_interventions_planting_id` (`planting_id`),
  KEY `product_id` (`product_id`),
  CONSTRAINT `interventions_ibfk_1` FOREIGN KEY (`planting_id`) REFERENCES `plantings` (`id`),
  CONSTRAINT `interventions_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `agri_catalog` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `scouting_observations` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `planting_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `metric_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `metric_value` decimal(10,4) NOT NULL,
  `observed_at` date NOT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_scouting_observations_planting_id` (`planting_id`),
  CONSTRAINT `scouting_observations_ibfk_1` FOREIGN KEY (`planting_id`) REFERENCES `plantings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `recommendations` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `planting_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rule_code` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trigger_snapshot` json NOT NULL,
  `recommendation_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `severity` enum('info','advisory','critical') COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('pending','acknowledged','followed','ignored') COLLATE utf8mb4_unicode_ci NOT NULL,
  `farmer_feedback_note` text COLLATE utf8mb4_unicode_ci,
  `generated_at` datetime NOT NULL,
  `responded_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `confidence` enum('low','medium','verified') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_recommendations_planting_id` (`planting_id`),
  CONSTRAINT `recommendations_ibfk_1` FOREIGN KEY (`planting_id`) REFERENCES `plantings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `scheme_matches` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `scheme_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `matched_at` datetime NOT NULL,
  `status` enum('matched','viewed','dismissed','claimed') COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `match_confidence` enum('verified','provisional') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_scheme_matches_scheme_id` (`scheme_id`),
  KEY `ix_scheme_matches_user_id` (`user_id`),
  CONSTRAINT `scheme_matches_ibfk_1` FOREIGN KEY (`scheme_id`) REFERENCES `govt_schemes` (`id`),
  CONSTRAINT `scheme_matches_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

