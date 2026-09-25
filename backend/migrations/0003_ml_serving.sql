-- Serving the shipped ML models (ml/serving/, proxied by src/routes/ml.js).
--
-- crops.ml_key: the crop's key in the ML layer (ml/prep/common.py crop_key).
-- Model outputs name crops by this key; joining on it replaces matching on
-- display names, which broke on "Ragi (Finger Millet)" vs "ragi".
ALTER TABLE `crops`
  ADD COLUMN `ml_key` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL AFTER `name`;

UPDATE `crops` SET `ml_key` = 'rice' WHERE `name` = 'Rice';
UPDATE `crops` SET `ml_key` = 'ragi' WHERE `name` = 'Ragi (Finger Millet)';
UPDATE `crops` SET `ml_key` = 'maize' WHERE `name` = 'Maize';
UPDATE `crops` SET `ml_key` = 'cotton' WHERE `name` = 'Cotton';
UPDATE `crops` SET `ml_key` = 'sugarcane' WHERE `name` = 'Sugarcane';

-- Photos are stored for the farmer's own history regardless. This flag only
-- records consent to use them for retraining (ml/UNBLOCKING_PARKED_MODELS.md
-- section 1: consent must exist before any farmer photo reaches training).
ALTER TABLE `users`
  ADD COLUMN `photo_training_consent` tinyint(1) NOT NULL DEFAULT 0;

-- One row per model call that the app made on a farmer's behalf. ML output is
-- kept here, never in `recommendations`: that table is rule-engine output, FK'd
-- to plantings, with a confidence enum the model labels do not fit.
CREATE TABLE `ml_inferences` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `field_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `planting_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `model` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `crop_key` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `image_path` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `image_sha256` char(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `request_json` json DEFAULT NULL,
  `response_json` json DEFAULT NULL,
  `outcome` enum('ok','refused','error') COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_ml_inferences_user_created` (`user_id`, `created_at`),
  KEY `ix_ml_inferences_planting_id` (`planting_id`),
  CONSTRAINT `ml_inferences_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `ml_inferences_ibfk_2` FOREIGN KEY (`field_id`) REFERENCES `fields` (`id`),
  CONSTRAINT `ml_inferences_ibfk_3` FOREIGN KEY (`planting_id`) REFERENCES `plantings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
