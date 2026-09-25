-- Tie-breaker for "the field's latest soil test". tested_at is second-precision
-- (naive UTC by project convention), so two tests saved in the same second -
-- e.g. a farmer correcting a card straight away - were returned in arbitrary
-- order and the older, partial one could win. seq preserves insertion order.
ALTER TABLE `soil_tests`
  ADD COLUMN `seq` bigint unsigned NOT NULL AUTO_INCREMENT,
  ADD UNIQUE KEY `uq_soil_tests_seq` (`seq`);
