-- Run as root:  mysql -u root -p < setup_readonly_user.sql
-- Gives the agent SELECT-only access, so even a bad generated query cannot change data.

CREATE USER IF NOT EXISTS 'root'@'localhost' IDENTIFIED BY 'srec';
GRANT SELECT ON ecommerce.* TO 'root'@'localhost';
FLUSH PRIVILEGES;