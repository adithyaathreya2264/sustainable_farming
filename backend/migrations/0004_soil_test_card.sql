-- The rest of a soil-test card, for the soil-fertility model (5b,
-- ml/algorithms/soil_fertility_prediction.py), which needs all 12 values.
-- Units as printed on Indian soil health cards: EC dS/m, organic carbon %,
-- S/Zn/Fe/Cu/Mn/B ppm. All nullable: most farmers will only have N/P/K/pH,
-- and the app then says which values are missing instead of guessing them.
ALTER TABLE `soil_tests`
  ADD COLUMN `ec` decimal(10,3) DEFAULT NULL AFTER `ph`,
  ADD COLUMN `organic_carbon` decimal(10,3) DEFAULT NULL AFTER `ec`,
  ADD COLUMN `sulphur` decimal(10,3) DEFAULT NULL AFTER `organic_carbon`,
  ADD COLUMN `zinc` decimal(10,3) DEFAULT NULL AFTER `sulphur`,
  ADD COLUMN `iron` decimal(10,3) DEFAULT NULL AFTER `zinc`,
  ADD COLUMN `copper` decimal(10,3) DEFAULT NULL AFTER `iron`,
  ADD COLUMN `manganese` decimal(10,3) DEFAULT NULL AFTER `copper`,
  ADD COLUMN `boron` decimal(10,3) DEFAULT NULL AFTER `manganese`;
