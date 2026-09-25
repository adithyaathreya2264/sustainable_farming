-- Optional farmer-entered soil test results per field. Feeds the crop
-- recommendation endpoint (GET /api/v1/plantings/recommend-crop in src/routes/plantings.js);
-- when a field has no row here, that endpoint falls back to generic,
-- non-location-specific N/P/K/pH defaults rather than blocking.
CREATE TABLE `soil_tests` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `field_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nitrogen` decimal(10,3) DEFAULT NULL,
  `phosphorus` decimal(10,3) DEFAULT NULL,
  `potassium` decimal(10,3) DEFAULT NULL,
  `ph` decimal(4,2) DEFAULT NULL,
  `tested_at` datetime NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_soil_tests_field_id` (`field_id`),
  CONSTRAINT `soil_tests_ibfk_1` FOREIGN KEY (`field_id`) REFERENCES `fields` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
