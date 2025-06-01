-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: May 31, 2025 at 04:43 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `gradeai`
--

-- --------------------------------------------------------

--
-- Table structure for table `announcement`
--

CREATE TABLE `announcement` (
  `announcement_id` varchar(255) NOT NULL,
  `class_id` varchar(255) NOT NULL,
  `content` text DEFAULT NULL,
  `posted_at` datetime NOT NULL,
  `title` varchar(100) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `assignment`
--

CREATE TABLE `assignment` (
  `assignment_id` varchar(255) NOT NULL,
  `title` varchar(255) NOT NULL,
  `description` varchar(1000) DEFAULT NULL,
  `deadline` datetime NOT NULL,
  `class_id` varchar(255) NOT NULL,
  `total_score` int(11) DEFAULT NULL,
  `file_type` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `assignment`
--

INSERT INTO `assignment` (`assignment_id`, `title`, `description`, `deadline`, `class_id`, `total_score`, `file_type`) VALUES
('COMP1111_32c66bbd9df7', 'Racism', 'Students must write an essay about racism', '2025-05-31 23:59:00', 'COMP1111', 100, NULL),
('COMP1111_70dec0af9355', 'Climate Change', 'Students must write an essay about Climate Change', '2025-05-31 11:11:00', 'COMP1111', 100, NULL),
('COMP1111_ebc28e5ec6c7', 'World Peace', 'Write an essay about world peace', '2025-06-07 11:11:00', 'COMP1111', 123, NULL),
('COMP2112_73f997755658', 'Something', 'Write an essay about something', '2025-06-12 11:11:00', 'COMP2112', 100, 'PDF');

-- --------------------------------------------------------

--
-- Table structure for table `class`
--

CREATE TABLE `class` (
  `class_id` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `created_at` datetime NOT NULL,
  `teacher_id` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `class`
--

INSERT INTO `class` (`class_id`, `name`, `created_at`, `teacher_id`) VALUES
('COMP1111', 'OOP', '2025-05-30 17:02:38', 'admin'),
('COMP2112', 'Data Structures', '2025-05-31 16:54:13', 'admin');

-- --------------------------------------------------------

--
-- Table structure for table `enrollment`
--

CREATE TABLE `enrollment` (
  `enrollment_id` varchar(255) NOT NULL,
  `enrolled_at` datetime DEFAULT NULL,
  `class_id` varchar(255) DEFAULT NULL,
  `student_id` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `enrollment`
--

INSERT INTO `enrollment` (`enrollment_id`, `enrolled_at`, `class_id`, `student_id`) VALUES
('COMP1111_21SOFT1013', '2025-05-30 17:02:38', 'COMP1111', '21SOFT1013'),
('COMP1111_21SOFT1028', '2025-05-30 17:02:38', 'COMP1111', '21SOFT1028'),
('COMP2112_21SOFT1013', '2025-05-31 16:54:13', 'COMP2112', '21SOFT1013'),
('COMP2112_21SOFT1028', '2025-05-31 16:54:13', 'COMP2112', '21SOFT1028');

-- --------------------------------------------------------

--
-- Table structure for table `grade`
--

CREATE TABLE `grade` (
  `grade_id` varchar(255) NOT NULL,
  `submission_id` varchar(255) NOT NULL,
  `score` int(11) DEFAULT NULL,
  `feedback` varchar(1000) DEFAULT NULL,
  `teacher_id` varchar(255) DEFAULT NULL,
  `adjusted_at` datetime DEFAULT NULL,
  `is_adjusted` bit(1) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `grade`
--

INSERT INTO `grade` (`grade_id`, `submission_id`, `score`, `feedback`, `teacher_id`, `adjusted_at`, `is_adjusted`) VALUES
('grade_COMP1111_ebc28e5ec6c7_21SOFT1013_dfd7ccc6', 'COMP1111_ebc28e5ec6c7_21SOFT1013_dfd7ccc6', 25, 'This submission is graded by system!', 'admin', NULL, b'0');

-- --------------------------------------------------------

--
-- Table structure for table `rubric`
--

CREATE TABLE `rubric` (
  `rubric_id` varchar(255) NOT NULL,
  `score` float NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `created_by` varchar(255) DEFAULT NULL,
  `assignment_id` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `rubric`
--

INSERT INTO `rubric` (`rubric_id`, `score`, `description`, `created_at`, `created_by`, `assignment_id`) VALUES
('rubric_COMP1111_32c66bbd9df7_000', 25, 'Clear thesis statement and main argument', '2025-05-31 00:26:24', 'admin', 'COMP1111_32c66bbd9df7'),
('rubric_COMP1111_32c66bbd9df7_001', 25, 'Strong supporting evidence and examples', '2025-05-31 00:26:24', 'admin', 'COMP1111_32c66bbd9df7'),
('rubric_COMP1111_32c66bbd9df7_002', 20, 'Logical organization and flow', '2025-05-31 00:26:24', 'admin', 'COMP1111_32c66bbd9df7'),
('rubric_COMP1111_32c66bbd9df7_003', 15, 'Grammar, style, and writing mechanics', '2025-05-31 00:26:24', 'admin', 'COMP1111_32c66bbd9df7'),
('rubric_COMP1111_32c66bbd9df7_004', 15, 'Critical analysis and depth of thought', '2025-05-31 00:26:24', 'admin', 'COMP1111_32c66bbd9df7'),
('rubric_COMP1111_70dec0af9355_000', 25, 'Clear thesis statement and main argument', '2025-05-31 01:47:42', 'admin', 'COMP1111_70dec0af9355'),
('rubric_COMP1111_70dec0af9355_001', 25, 'Strong supporting evidence and examples', '2025-05-31 01:47:42', 'admin', 'COMP1111_70dec0af9355'),
('rubric_COMP1111_70dec0af9355_002', 20, 'Logical organization and flow', '2025-05-31 01:47:42', 'admin', 'COMP1111_70dec0af9355'),
('rubric_COMP1111_70dec0af9355_003', 15, 'Grammar, style, and writing mechanics', '2025-05-31 01:47:42', 'admin', 'COMP1111_70dec0af9355'),
('rubric_COMP1111_70dec0af9355_004', 15, 'Critical analysis and depth of thought', '2025-05-31 01:47:42', 'admin', 'COMP1111_70dec0af9355'),
('rubric_COMP1111_ebc28e5ec6c7_000', 18, 'Clearly states the topic or issue being addressed', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP1111_ebc28e5ec6c7_001', 17, 'Provides specific details about the subject matter', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP1111_ebc28e5ec6c7_002', 16, 'Organizes ideas logically using transitional phrases and sentences', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP1111_ebc28e5ec6c7_003', 14, 'Uses proper grammar, spelling, punctuation, and capitalization throughout', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP1111_ebc28e5ec6c7_004', 12, 'Presents logical connections between paragraphs', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP1111_ebc28e5ec6c7_005', 22, 'Demonstrates effective use of supporting evidence from credible sources to support claims', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP1111_ebc28e5ec6c7_006', 13, 'Addresses counterarguments effectively by acknowledging opposing views', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP1111_ebc28e5ec6c7_007', 11, 'Writing is clear, concise, and free of unnecessary words; uses active voice when appropriate', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP1111_ebc28e5ec6c7_008', 0, 'Adheres strictly to word count guidelines as specified in instructions', '2025-05-30 17:44:02', 'admin', 'COMP1111_ebc28e5ec6c7'),
('rubric_COMP2112_73f997755658_000', 25, 'Clear thesis statement and main argument', '2025-05-31 17:41:03', 'admin', 'COMP2112_73f997755658'),
('rubric_COMP2112_73f997755658_001', 25, 'Strong supporting evidence and examples', '2025-05-31 17:41:03', 'admin', 'COMP2112_73f997755658'),
('rubric_COMP2112_73f997755658_002', 20, 'Logical organization and flow', '2025-05-31 17:41:03', 'admin', 'COMP2112_73f997755658'),
('rubric_COMP2112_73f997755658_003', 15, 'Grammar, style, and writing mechanics', '2025-05-31 17:41:03', 'admin', 'COMP2112_73f997755658'),
('rubric_COMP2112_73f997755658_004', 15, 'Critical analysis and depth of thought', '2025-05-31 17:41:03', 'admin', 'COMP2112_73f997755658');

-- --------------------------------------------------------

--
-- Table structure for table `submission`
--

CREATE TABLE `submission` (
  `submission_id` varchar(255) NOT NULL,
  `assignment_id` varchar(255) NOT NULL,
  `submitted_at` datetime DEFAULT NULL,
  `status` bit(1) NOT NULL,
  `student_id` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `submission`
--

INSERT INTO `submission` (`submission_id`, `assignment_id`, `submitted_at`, `status`, `student_id`) VALUES
('COMP1111_ebc28e5ec6c7_21SOFT1013_dfd7ccc6', 'COMP1111_ebc28e5ec6c7', '2025-05-31 17:39:56', b'1', '21SOFT1013');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `user_id` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `first_name` varchar(255) NOT NULL,
  `last_name` varchar(255) NOT NULL,
  `role` bit(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `last_login` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`user_id`, `email`, `password`, `first_name`, `last_name`, `role`, `created_at`, `last_login`) VALUES
('21SOFT1013', '21SOFT1013@isik.edu.tr', '5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5', 'Cansu', 'Kars', b'0', '2025-05-01 14:37:36', '2025-05-31 17:41:14'),
('21SOFT1028', '21SOFT1028@isik.edu.tr', '5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5', 'Orhan ', 'Tuncer', b'0', '2025-04-26 11:28:02', '2025-05-30 16:24:55'),
('admin', 'admin@adminun.edu.tr', '5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5', 'admin', 'adminn', b'1', '2025-04-27 12:55:29', '2025-05-31 17:40:11');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `announcement`
--
ALTER TABLE `announcement`
  ADD PRIMARY KEY (`announcement_id`),
  ADD KEY `class_id` (`class_id`);

--
-- Indexes for table `assignment`
--
ALTER TABLE `assignment`
  ADD PRIMARY KEY (`assignment_id`),
  ADD UNIQUE KEY `title` (`title`),
  ADD KEY `class_id` (`class_id`);

--
-- Indexes for table `class`
--
ALTER TABLE `class`
  ADD PRIMARY KEY (`class_id`),
  ADD UNIQUE KEY `name` (`name`),
  ADD KEY `teacher_id` (`teacher_id`);

--
-- Indexes for table `enrollment`
--
ALTER TABLE `enrollment`
  ADD PRIMARY KEY (`enrollment_id`),
  ADD KEY `student_id` (`student_id`),
  ADD KEY `class_id` (`class_id`);

--
-- Indexes for table `grade`
--
ALTER TABLE `grade`
  ADD PRIMARY KEY (`grade_id`),
  ADD KEY `submission_id` (`submission_id`),
  ADD KEY `teacher_id` (`teacher_id`);

--
-- Indexes for table `rubric`
--
ALTER TABLE `rubric`
  ADD PRIMARY KEY (`rubric_id`),
  ADD KEY `created_by` (`created_by`),
  ADD KEY `fk_rassid_assid` (`assignment_id`);

--
-- Indexes for table `submission`
--
ALTER TABLE `submission`
  ADD PRIMARY KEY (`submission_id`),
  ADD KEY `student_id` (`student_id`),
  ADD KEY `assignment_id` (`assignment_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`user_id`),
  ADD UNIQUE KEY `email` (`email`);

--
-- Constraints for dumped tables
--

--
-- Constraints for table `announcement`
--
ALTER TABLE `announcement`
  ADD CONSTRAINT `Announcement_ibfk_1` FOREIGN KEY (`class_id`) REFERENCES `class` (`class_id`);

--
-- Constraints for table `assignment`
--
ALTER TABLE `assignment`
  ADD CONSTRAINT `Assignment_ibfk_1` FOREIGN KEY (`class_id`) REFERENCES `class` (`class_id`);

--
-- Constraints for table `class`
--
ALTER TABLE `class`
  ADD CONSTRAINT `Class_ibfk_1` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`user_id`);

--
-- Constraints for table `enrollment`
--
ALTER TABLE `enrollment`
  ADD CONSTRAINT `Enrollment_ibfk_3` FOREIGN KEY (`class_id`) REFERENCES `class` (`class_id`);

--
-- Constraints for table `grade`
--
ALTER TABLE `grade`
  ADD CONSTRAINT `Grade_ibfk_3` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`user_id`);

--
-- Constraints for table `rubric`
--
ALTER TABLE `rubric`
  ADD CONSTRAINT `Rubric_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`),
  ADD CONSTRAINT `fk_rassid_assid` FOREIGN KEY (`assignment_id`) REFERENCES `assignment` (`assignment_id`);

--
-- Constraints for table `submission`
--
ALTER TABLE `submission`
  ADD CONSTRAINT `Submission_ibfk_2` FOREIGN KEY (`student_id`) REFERENCES `users` (`user_id`),
  ADD CONSTRAINT `Submission_ibfk_3` FOREIGN KEY (`assignment_id`) REFERENCES `assignment` (`assignment_id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
