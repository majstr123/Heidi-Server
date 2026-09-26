-- Heidi Server -- nalogi database structure recreate
-- Generated 2026-09-26 via: mysqldump --no-data --routines --triggers --events
-- against the live production DB (192.168.52.104:33062/nalogi, MySQL 5.7).
-- Structure only -- no data. Recreates every table/trigger the server code
-- and Heidi-PE/Heidi-SM actually use.


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `custom_sheet_sizes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `custom_sheet_sizes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `length` double NOT NULL,
  `width` double NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_length_width` (`length`,`width`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `customer_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `customer_data` (
  `id` smallint(6) NOT NULL,
  `title` varchar(200) COLLATE utf8_slovenian_ci NOT NULL,
  `address` varchar(200) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `house_number` varchar(20) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `city` varchar(50) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `country_id` varchar(10) COLLATE utf8_slovenian_ci NOT NULL,
  `country` varchar(30) COLLATE utf8_slovenian_ci NOT NULL,
  `postal_code` varchar(10) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `post` varchar(30) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `social_security_number` varchar(10) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `vat_number` varchar(20) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `alias` varchar(200) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `title_short` varchar(50) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `phone` varchar(50) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `mail` varchar(50) COLLATE utf8_slovenian_ci DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `id` (`id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_slovenian_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cut_list_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cut_list_items` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `material` varchar(100) DEFAULT NULL,
  `thickness` double DEFAULT NULL,
  `qty` int(11) NOT NULL DEFAULT '1',
  `customer` varchar(255) NOT NULL DEFAULT '',
  `project` varchar(255) NOT NULL DEFAULT '',
  `source_path` varchar(1024) NOT NULL,
  `added_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_source_customer_project` (`source_path`(255),`customer`,`project`)
) ENGINE=InnoDB AUTO_INCREMENT=168 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cutting_tickets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cutting_tickets` (
  `Id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `Sheet` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Qty` varchar(20) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Customer` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Machine` varchar(10) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL COMMENT 'Laser/Plazma',
  `Create_Date` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Completion_Time` varchar(300) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Project` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `CNC` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Report` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Completed_Flag` varchar(10) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `ReportData` json DEFAULT NULL,
  `Remanant_scrapped` binary(20) DEFAULT NULL,
  PRIMARY KEY (`Id`) USING BTREE,
  UNIQUE KEY `idnew_table_UNIQUE` (`Id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=4710 DEFAULT CHARSET=armscii8 COLLATE=armscii8_bin ROW_FORMAT=DYNAMIC;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `fasteners`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fasteners` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `standard` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `thread` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `length_mm` decimal(10,2) DEFAULT NULL,
  `grade` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `finish` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `supplier_code` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `price` decimal(12,4) DEFAULT NULL,
  `price_unit` enum('€/pc','€/cnt','€/box') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '€/pc',
  `pack_qty` int(10) unsigned DEFAULT NULL,
  `order_unit` enum('pc','cnt','box') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pc',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`Id`),
  UNIQUE KEY `uq_fastener_identity` (`name`,`standard`,`thread`,`length_mm`,`grade`,`finish`),
  KEY `idx_fasteners_name` (`name`),
  KEY `idx_fasteners_supplier_code` (`supplier_code`)
) ENGINE=InnoDB AUTO_INCREMENT=513 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `global_parts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `global_parts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `customer` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `material` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `thickness` double NOT NULL DEFAULT '0',
  `project` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `geometry_hash` char(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `bbox_width` double NOT NULL DEFAULT '0',
  `bbox_height` double NOT NULL DEFAULT '0',
  `entity_count` int(11) NOT NULL DEFAULT '0',
  `source_path` varchar(1024) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `hprt_path` varchar(1024) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_customer` (`customer`),
  KEY `idx_geometry_hash` (`geometry_hash`),
  KEY `idx_name` (`name`),
  FULLTEXT KEY `idx_search` (`name`,`customer`,`material`,`project`)
) ENGINE=InnoDB AUTO_INCREMENT=447 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `global_sheets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `global_sheets` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `material` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `thickness` double NOT NULL DEFAULT '0',
  `sheet_width` double NOT NULL DEFAULT '0',
  `sheet_height` double NOT NULL DEFAULT '0',
  `part_count` int(11) NOT NULL DEFAULT '0',
  `qty` int(11) NOT NULL DEFAULT '1',
  `is_custom` tinyint(1) NOT NULL DEFAULT '0',
  `rel_path` varchar(1024) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_material` (`material`),
  KEY `idx_name` (`name`),
  FULLTEXT KEY `idx_search` (`name`,`material`)
) ENGINE=InnoDB AUTO_INCREMENT=67 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `material`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `material` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `Item` varchar(50) CHARACTER SET utf8 COLLATE utf8_slovenian_ci NOT NULL DEFAULT '0',
  `Material` varchar(50) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT '0',
  `Measure-Quantity` float NOT NULL DEFAULT '0',
  `Unit` varchar(20) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Price` float DEFAULT NULL,
  `Em` varchar(20) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `CrossSection-Thickness` float DEFAULT NULL,
  `SolidWorksKey` varchar(100) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Type` varchar(15) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `orderUnit` varchar(20) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  PRIMARY KEY (`Id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=3951 DEFAULT CHARSET=armscii8 COLLATE=armscii8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`Jure`@`%`*/ /*!50003 TRIGGER `trg_material_em_valid_before_insert` BEFORE INSERT ON `material` FOR EACH ROW BEGIN
    IF NEW.Em IS NOT NULL AND NEW.Em != '' AND NEW.Em != '0' THEN
        IF NEW.Em NOT IN (
            '€/m', '€/kg', '€/pcs', '€/pc', '€/piece',
            '€/m²', '€/m2', '€/m³', '€/m3',
            '€/sheet',
            '€/h', '€/hour', '€/min',
            '€/t', '€/ton',
            '€/l',
            '€/g',
            '€/ml',
            '€/cm',
            '€/pal', '€/pallet',
            '€/set',
            '€/roll',
            '€/bar',
            '€/profile',
            '€/km'
        ) THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid unit. Allowed units are: €/m, €/kg, €/pcs, €/pc, €/piece, €/m², €/m2, €/m³, €/m3, €/sheet, €/h, €/hour, €/min, €/t, €/ton, €/l, €/g, €/ml, €/cm, €/pal, €/pallet, €/set, €/roll, €/bar, €/profile';
        END IF;
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`Jure`@`%`*/ /*!50003 TRIGGER `trg_material_em_valid_before_update` BEFORE UPDATE ON `material` FOR EACH ROW BEGIN
    IF NEW.Em IS NOT NULL AND NEW.Em != '' AND NEW.Em != '0' THEN
        IF NEW.Em NOT IN (
            '€/m', '€/kg', '€/pcs', '€/pc', '€/piece',
            '€/m²', '€/m2', '€/m³', '€/m3',
            '€/sheet',
            '€/h', '€/hour', '€/min',
            '€/t', '€/ton',
            '€/l',
            '€/g',
            '€/ml',
            '€/cm',
            '€/pal', '€/pallet',
            '€/set',
            '€/roll',
            '€/bar',
            '€/profile',
            '€/km'
        ) THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid unit. Allowed units are: €/m, €/kg, €/pcs, €/pc, €/piece, €/m², €/m2, €/m³, €/m3, €/sheet, €/h, €/hour, €/min, €/t, €/ton, €/l, €/g, €/ml, €/cm, €/pal, €/pallet, €/set, €/roll, €/bar, €/profile';
        END IF;
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
DROP TABLE IF EXISTS `material_order`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `material_order` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `project_id` int(11) DEFAULT NULL,
  `material_id` int(11) DEFAULT NULL,
  `qty` float DEFAULT NULL,
  `unit` varchar(20) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `price` int(11) DEFAULT NULL,
  `Em` varchar(20) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `order_flag` tinyint(1) DEFAULT '0',
  `delivery_flag` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`Id`),
  UNIQUE KEY `Id` (`Id`),
  KEY `project_id` (`project_id`),
  KEY `material_id` (`material_id`),
  CONSTRAINT `material_order_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `projects` (`Id`) ON DELETE CASCADE,
  CONSTRAINT `material_order_ibfk_2` FOREIGN KEY (`material_id`) REFERENCES `material` (`Id`)
) ENGINE=InnoDB AUTO_INCREMENT=70 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `material_price`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `material_price` (
  `Id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `Material` varchar(50) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Type` varchar(50) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Price` varchar(30) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Unit` varchar(12) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `density` float DEFAULT NULL,
  `density_ref` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`Id`),
  UNIQUE KEY `Id` (`Id`)
) ENGINE=InnoDB AUTO_INCREMENT=51 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `nalogi`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `nalogi` (
  `Id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `Plošča` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Količina` varchar(20) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Stranka` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Naprava` varchar(10) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL COMMENT 'Laser/Plazma',
  `Datum vnosa` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `čas izdelave` varchar(45) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Komentar` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Datoteka` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Poročilo` varchar(200) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Obračun` varchar(10) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `ReportData` json DEFAULT NULL,
  PRIMARY KEY (`Id`),
  UNIQUE KEY `idnew_table_UNIQUE` (`Id`)
) ENGINE=InnoDB AUTO_INCREMENT=3494 DEFAULT CHARSET=armscii8 COLLATE=armscii8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `postnestevilke`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `postnestevilke` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `number` int(11) NOT NULL DEFAULT '0',
  `city` varchar(50) COLLATE utf8_slovenian_ci NOT NULL DEFAULT '0',
  `country` varchar(50) COLLATE utf8_slovenian_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=479 DEFAULT CHARSET=utf8 COLLATE=utf8_slovenian_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `project_order_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `project_order_items` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `project_id` int(11) NOT NULL,
  `source_material_id` int(11) DEFAULT NULL,
  `item` varchar(255) COLLATE utf8_slovenian_ci NOT NULL,
  `material` varchar(255) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `type` varchar(50) COLLATE utf8_slovenian_ci NOT NULL DEFAULT 'item',
  `order_mode` enum('unit','area','sheets') COLLATE utf8_slovenian_ci NOT NULL DEFAULT 'unit',
  `qty_value` decimal(18,4) DEFAULT '0.0000',
  `qty_unit` varchar(20) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `unit_price_value` decimal(18,4) DEFAULT '0.0000',
  `unit_price_unit` varchar(20) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `total_price_value` decimal(18,4) DEFAULT '0.0000',
  `total_price_unit` varchar(10) COLLATE utf8_slovenian_ci NOT NULL DEFAULT 'EUR',
  `order_flag` tinyint(1) NOT NULL DEFAULT '0',
  `delivery_flag` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `ordered_at` datetime DEFAULT NULL,
  `delivered_at` datetime DEFAULT NULL,
  `sheet_mode` varchar(16) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `sheet_count` double DEFAULT NULL,
  `sheet_width_mm` double DEFAULT NULL,
  `sheet_height_mm` double DEFAULT NULL,
  `sheet_waste_percent` double DEFAULT NULL,
  `sheet_size` varchar(64) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `order_unit` varchar(32) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `source_file_path` varchar(500) COLLATE utf8_slovenian_ci DEFAULT NULL,
  PRIMARY KEY (`Id`),
  KEY `idx_poi_project` (`project_id`),
  KEY `idx_poi_type_mode` (`type`,`order_mode`),
  KEY `idx_poi_order_delivery` (`order_flag`,`delivery_flag`),
  KEY `idx_poi_material` (`material`),
  KEY `idx_poi_source_material` (`source_material_id`),
  CONSTRAINT `fk_poi_project` FOREIGN KEY (`project_id`) REFERENCES `projects` (`Id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=127 DEFAULT CHARSET=utf8 COLLATE=utf8_slovenian_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`Jure`@`%`*/ /*!50003 TRIGGER `bi_project_order_items_defaults`
BEFORE INSERT ON `project_order_items`
FOR EACH ROW
BEGIN
    SET NEW.type = LOWER(TRIM(COALESCE(NEW.type, 'item')));

    IF NEW.created_at IS NULL THEN
        SET NEW.created_at = NOW();
    END IF;
    SET NEW.updated_at = NOW();

    IF NEW.order_flag = 1 AND NEW.ordered_at IS NULL THEN
        SET NEW.ordered_at = NOW();
    END IF;

    IF NEW.delivery_flag = 1 AND NEW.delivered_at IS NULL THEN
        SET NEW.delivered_at = NOW();
    END IF;

    IF NEW.order_flag = 0 THEN
        SET NEW.ordered_at = NULL;
    END IF;

    IF NEW.delivery_flag = 0 THEN
        SET NEW.delivered_at = NULL;
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`Jure`@`%`*/ /*!50003 TRIGGER `bu_project_order_items_defaults`
BEFORE UPDATE ON `project_order_items`
FOR EACH ROW
BEGIN
    SET NEW.type = LOWER(TRIM(COALESCE(NEW.type, OLD.type)));
    SET NEW.updated_at = NOW();

    IF OLD.order_flag = 0 AND NEW.order_flag = 1 THEN
        SET NEW.ordered_at = NOW();
    ELSEIF NEW.order_flag = 0 THEN
        SET NEW.ordered_at = NULL;
    END IF;

    IF OLD.delivery_flag = 0 AND NEW.delivery_flag = 1 THEN
        SET NEW.delivered_at = NOW();
    ELSEIF NEW.delivery_flag = 0 THEN
        SET NEW.delivered_at = NULL;
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
DROP TABLE IF EXISTS `project_order_sheetmetal`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `project_order_sheetmetal` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `order_item_id` int(11) NOT NULL,
  `sheet_size_id` int(10) unsigned DEFAULT NULL,
  `sheet_length_mm` decimal(12,3) DEFAULT NULL,
  `sheet_width_mm` decimal(12,3) DEFAULT NULL,
  `thickness_mm` decimal(12,3) DEFAULT NULL,
  `requested_area_m2` decimal(18,4) DEFAULT NULL,
  `sheet_count` decimal(18,4) DEFAULT NULL,
  `effective_area_m2` decimal(18,4) DEFAULT NULL,
  `waste_pct` decimal(7,3) NOT NULL DEFAULT '0.000',
  `price_per_m2_snapshot` decimal(18,4) DEFAULT NULL,
  `currency` varchar(10) COLLATE utf8_slovenian_ci NOT NULL DEFAULT 'EUR',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`Id`),
  UNIQUE KEY `uq_posm_order_item` (`order_item_id`),
  KEY `idx_posm_sheet_size` (`sheet_size_id`),
  CONSTRAINT `fk_posm_order_item` FOREIGN KEY (`order_item_id`) REFERENCES `project_order_items` (`Id`) ON DELETE CASCADE,
  CONSTRAINT `fk_posm_sheet_size` FOREIGN KEY (`sheet_size_id`) REFERENCES `sheet_sizes` (`Id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_slovenian_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`Jure`@`%`*/ /*!50003 TRIGGER `bi_project_order_sheetmetal_validate`
BEFORE INSERT ON `project_order_sheetmetal`
FOR EACH ROW
BEGIN
    DECLARE v_type VARCHAR(50);
    DECLARE v_mode VARCHAR(20);

    DECLARE v_len DECIMAL(12,3);
    DECLARE v_wid DECIMAL(12,3);
    DECLARE v_thk DECIMAL(12,3);

    SELECT LOWER(type), order_mode
      INTO v_type, v_mode
      FROM project_order_items
     WHERE Id = NEW.order_item_id;

    IF v_type <> 'sheetmetal' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'project_order_sheetmetal row requires parent type=sheetmetal';
    END IF;

    -- Pull snapshot dimensions from sheet_sizes if chosen
    IF NEW.sheet_size_id IS NOT NULL THEN
        SELECT Length, Width, Thickness
          INTO v_len, v_wid, v_thk
          FROM sheet_sizes
         WHERE Id = NEW.sheet_size_id;

        IF NEW.sheet_length_mm IS NULL THEN SET NEW.sheet_length_mm = v_len; END IF;
        IF NEW.sheet_width_mm  IS NULL THEN SET NEW.sheet_width_mm  = v_wid; END IF;
        IF NEW.thickness_mm    IS NULL THEN SET NEW.thickness_mm    = v_thk; END IF;
    END IF;

    IF v_mode = 'area' THEN
        IF NEW.requested_area_m2 IS NULL OR NEW.requested_area_m2 <= 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Area mode requires requested_area_m2 > 0';
        END IF;
        SET NEW.effective_area_m2 = NEW.requested_area_m2 * (1 + (COALESCE(NEW.waste_pct,0) / 100));
    ELSEIF v_mode = 'sheets' THEN
        IF NEW.sheet_count IS NULL OR NEW.sheet_count <= 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Sheets mode requires sheet_count > 0';
        END IF;
        IF NEW.sheet_length_mm IS NULL OR NEW.sheet_width_mm IS NULL THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Sheets mode requires sheet dimensions';
        END IF;
        SET NEW.effective_area_m2 =
            ((NEW.sheet_length_mm * NEW.sheet_width_mm) / 1000000.0)
            * NEW.sheet_count
            * (1 + (COALESCE(NEW.waste_pct,0) / 100));
    ELSE
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Sheetmetal parent order_mode must be area or sheets';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`Jure`@`%`*/ /*!50003 TRIGGER `ai_project_order_sheetmetal_sync_parent`
AFTER INSERT ON `project_order_sheetmetal`
FOR EACH ROW
BEGIN
    UPDATE project_order_items poi
       SET poi.qty_value = NEW.effective_area_m2,
           poi.qty_unit = 'm2',
           poi.unit_price_unit = COALESCE(poi.unit_price_unit, '€/m²'),
           poi.total_price_value = ROUND(COALESCE(NEW.effective_area_m2,0) * COALESCE(poi.unit_price_value,0), 4),
           poi.total_price_unit = COALESCE(poi.total_price_unit, NEW.currency, 'EUR')
     WHERE poi.Id = NEW.order_item_id;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`Jure`@`%`*/ /*!50003 TRIGGER `bu_project_order_sheetmetal_validate`
BEFORE UPDATE ON `project_order_sheetmetal`
FOR EACH ROW
BEGIN
    DECLARE v_type VARCHAR(50);
    DECLARE v_mode VARCHAR(20);

    DECLARE v_len DECIMAL(12,3);
    DECLARE v_wid DECIMAL(12,3);
    DECLARE v_thk DECIMAL(12,3);

    SELECT LOWER(type), order_mode
      INTO v_type, v_mode
      FROM project_order_items
     WHERE Id = NEW.order_item_id;

    IF v_type <> 'sheetmetal' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'project_order_sheetmetal row requires parent type=sheetmetal';
    END IF;

    IF NEW.sheet_size_id IS NOT NULL THEN
        SELECT Length, Width, Thickness
          INTO v_len, v_wid, v_thk
          FROM sheet_sizes
         WHERE Id = NEW.sheet_size_id;

        IF NEW.sheet_length_mm IS NULL THEN SET NEW.sheet_length_mm = v_len; END IF;
        IF NEW.sheet_width_mm  IS NULL THEN SET NEW.sheet_width_mm  = v_wid; END IF;
        IF NEW.thickness_mm    IS NULL THEN SET NEW.thickness_mm    = v_thk; END IF;
    END IF;

    IF v_mode = 'area' THEN
        IF NEW.requested_area_m2 IS NULL OR NEW.requested_area_m2 <= 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Area mode requires requested_area_m2 > 0';
        END IF;
        SET NEW.effective_area_m2 = NEW.requested_area_m2 * (1 + (COALESCE(NEW.waste_pct,0) / 100));
    ELSEIF v_mode = 'sheets' THEN
        IF NEW.sheet_count IS NULL OR NEW.sheet_count <= 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Sheets mode requires sheet_count > 0';
        END IF;
        IF NEW.sheet_length_mm IS NULL OR NEW.sheet_width_mm IS NULL THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Sheets mode requires sheet dimensions';
        END IF;
        SET NEW.effective_area_m2 =
            ((NEW.sheet_length_mm * NEW.sheet_width_mm) / 1000000.0)
            * NEW.sheet_count
            * (1 + (COALESCE(NEW.waste_pct,0) / 100));
    ELSE
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Sheetmetal parent order_mode must be area or sheets';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`Jure`@`%`*/ /*!50003 TRIGGER `au_project_order_sheetmetal_sync_parent`
AFTER UPDATE ON `project_order_sheetmetal`
FOR EACH ROW
BEGIN
    UPDATE project_order_items poi
       SET poi.qty_value = NEW.effective_area_m2,
           poi.qty_unit = 'm2',
           poi.unit_price_unit = COALESCE(poi.unit_price_unit, '€/m²'),
           poi.total_price_value = ROUND(COALESCE(NEW.effective_area_m2,0) * COALESCE(poi.unit_price_value,0), 4),
           poi.total_price_unit = COALESCE(poi.total_price_unit, NEW.currency, 'EUR')
     WHERE poi.Id = NEW.order_item_id;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
DROP TABLE IF EXISTS `projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `projects` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `project_title` varchar(200) COLLATE utf8_slovenian_ci NOT NULL,
  `subproject_title` varchar(200) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `customer_id` smallint(6) NOT NULL,
  `project_technical_path` text COLLATE utf8_slovenian_ci,
  `project_administration_path` varchar(255) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `project_ticket_paths` text COLLATE utf8_slovenian_ci,
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_edit` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted` tinyint(1) NOT NULL DEFAULT '0' COMMENT '0 = active, 1 = deleted',
  `deleted_at` timestamp NULL DEFAULT NULL COMMENT 'Timestamp when deleted',
  `project_code` varchar(10) COLLATE utf8_slovenian_ci NOT NULL,
  `display_year` varchar(4) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `status` varchar(30) COLLATE utf8_slovenian_ci DEFAULT NULL,
  `old_path` varchar(255) COLLATE utf8_slovenian_ci DEFAULT NULL,
  PRIMARY KEY (`Id`),
  UNIQUE KEY `project_code` (`project_code`),
  KEY `idx_customer_id` (`customer_id`),
  CONSTRAINT `fk_projects_customer` FOREIGN KEY (`customer_id`) REFERENCES `customer_data` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=308 DEFAULT CHARSET=utf8 COLLATE=utf8_slovenian_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_files`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `report_files` (
  `FileId` bigint(20) NOT NULL AUTO_INCREMENT,
  `NalogId` int(10) unsigned NOT NULL,
  `FileType` varchar(50) COLLATE armscii8_bin NOT NULL,
  `FilePath` varchar(255) COLLATE armscii8_bin NOT NULL,
  `FileData` mediumblob,
  PRIMARY KEY (`FileId`),
  UNIQUE KEY `NalogId` (`NalogId`,`FileType`,`FilePath`),
  KEY `idx_report_files_nalogid_filetype` (`NalogId`,`FileType`),
  CONSTRAINT `report_files_ibfk_1` FOREIGN KEY (`NalogId`) REFERENCES `nalogi` (`Id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=armscii8 COLLATE=armscii8_bin;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `services`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `services` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `price` double DEFAULT NULL,
  `price_unit` varchar(32) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`Id`),
  UNIQUE KEY `uq_services_name_unit` (`name`,`price_unit`)
) ENGINE=InnoDB AUTO_INCREMENT=89 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sheet_id_counters`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sheet_id_counters` (
  `material` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `thickness` double NOT NULL,
  `next_id` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`material`,`thickness`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sheet_locks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sheet_locks` (
  `sheet_id` int(11) NOT NULL,
  `user_name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `workspace_id` int(11) DEFAULT NULL,
  `client_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `acquired_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `heartbeat_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `release_requested_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `release_requested_at` datetime DEFAULT NULL,
  PRIMARY KEY (`sheet_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sheet_material_thickness`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sheet_material_thickness` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `material` varchar(100) NOT NULL,
  `thickness` double NOT NULL,
  `kerf_width` double NOT NULL DEFAULT '0.2',
  `lead_in_length` double NOT NULL DEFAULT '3',
  `lead_out_length` double NOT NULL DEFAULT '0',
  `end_gap_length` double NOT NULL DEFAULT '0',
  `bundle_data` longblob,
  `hash` varchar(64) DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `layer_ref` varchar(255) DEFAULT NULL,
  `kerf_width_internal` double DEFAULT NULL,
  `kerf_width_external` double DEFAULT NULL,
  `lead_in_type` varchar(20) DEFAULT NULL,
  `lead_in_angle` double DEFAULT NULL,
  `lead_in_arc_radius` double DEFAULT NULL,
  `lead_in_arc_angle` double DEFAULT NULL,
  `lead_out_type` varchar(20) DEFAULT NULL,
  `lead_out_angle` double DEFAULT NULL,
  `lead_out_arc_radius` double DEFAULT NULL,
  `lead_out_arc_angle` double DEFAULT NULL,
  `lead_out_overlap` double DEFAULT NULL,
  `pierce_time_sec` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_mat_thick` (`material`,`thickness`)
) ENGINE=InnoDB AUTO_INCREMENT=2522 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sheet_size_order`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sheet_size_order` (
  `length` double NOT NULL,
  `width` double NOT NULL,
  `sort_order` int(11) NOT NULL,
  PRIMARY KEY (`length`,`width`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sheet_sizes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sheet_sizes` (
  `Id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `Sheet_Type` varchar(50) COLLATE utf8_slovenian_ci NOT NULL DEFAULT '0',
  `Length` float NOT NULL DEFAULT '0',
  `Width` float NOT NULL DEFAULT '0',
  `Standard_Dimension` binary(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`Id`) USING BTREE,
  UNIQUE KEY `Id` (`Id`) USING BTREE,
  KEY `idx_sheet_sizes_type_len_wid` (`Sheet_Type`,`Length`,`Width`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=109 DEFAULT CHARSET=utf8 COLLATE=utf8_slovenian_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tags` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `tag` varchar(30) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `color` varchar(30) CHARACTER SET utf8 COLLATE utf8_slovenian_ci DEFAULT NULL,
  `Status_Display` binary(1) DEFAULT NULL,
  PRIMARY KEY (`Id`),
  UNIQUE KEY `Id` (`Id`)
) ENGINE=InnoDB AUTO_INCREMENT=1061 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ticket_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ticket_tags` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `Tag` varchar(30) COLLATE utf8_slovenian_ci NOT NULL,
  PRIMARY KEY (`Id`),
  UNIQUE KEY `Id` (`Id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8 COLLATE=utf8_slovenian_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `workspace_parts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `workspace_parts` (
  `workspace_id` int(11) NOT NULL,
  `part_id` int(11) NOT NULL,
  `needed_qty` int(11) NOT NULL DEFAULT '1',
  `ordering` int(11) NOT NULL DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`workspace_id`,`part_id`),
  KEY `idx_workspace` (`workspace_id`),
  KEY `idx_part` (`part_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `workspace_sheets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `workspace_sheets` (
  `workspace_id` int(11) NOT NULL,
  `sheet_id` int(11) NOT NULL,
  `ordering` int(11) NOT NULL DEFAULT '0',
  `is_draft` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`workspace_id`,`sheet_id`),
  KEY `idx_workspace` (`workspace_id`),
  KEY `idx_sheet` (`sheet_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `workspaces`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `workspaces` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` enum('material','project','quote') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'material',
  `material` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `thickness` double NOT NULL DEFAULT '0',
  `project_id` int(11) DEFAULT NULL,
  `customer_id` int(11) DEFAULT NULL,
  `hwsp_path` varchar(1024) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `owner` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_type` (`type`),
  KEY `idx_material` (`material`),
  KEY `idx_project` (`project_id`),
  KEY `idx_owner` (`owner`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 DROP PROCEDURE IF EXISTS `GenerateProjectCode` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`Jure`@`%` PROCEDURE `GenerateProjectCode`(IN p_year CHAR(4), OUT p_code VARCHAR(10))
BEGIN
    DECLARE v_index INT DEFAULT 1;
    DECLARE v_max_index INT DEFAULT NULL;  -- Explicit NULL
    SELECT MAX(CAST(IFNULL(SUBSTRING(project_code, 5), 0) AS UNSIGNED)) INTO v_max_index 
    FROM projects WHERE SUBSTRING(project_code, 1, 4) = p_year;
    IF v_max_index IS NOT NULL THEN
        SET v_index = v_max_index + 1;
    END IF;
    SET p_code = CONCAT(p_year, LPAD(v_index, 3, '0'));
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

