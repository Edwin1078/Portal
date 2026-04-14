
CREATE DATABASE IF NOT EXISTS dashboard_portal;
USE dashboard_portal;

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);

-- Permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role_id INT,
    status ENUM('pending', 'active', 'rejected') DEFAULT 'pending',
    must_change_password BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

-- User Permissions mapping (for granular control)
CREATE TABLE IF NOT EXISTS user_permissions (
    user_id INT,
    permission_id INT,
    PRIMARY KEY (user_id, permission_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

-- Insert default roles
INSERT IGNORE INTO roles (name, description) VALUES 
('Admin', 'Full system access'),
('User', 'Limited access to assigned dashboards');

-- Insert default permissions
INSERT IGNORE INTO permissions (name, description) VALUES 
('view_historico', 'Acesso al dashboard de Historico'),
('view_conceptos', 'Acesso al dashboard de Conceptos');

-- Admin user (Default password will be 'admin123' hashed later)
-- Note: Register a user first, then promote manually to Admin:
-- UPDATE users SET role_id = 1 WHERE email = 'tu.email@admin.com';
-- AND ensure role_id = 1 is Admin in the 'roles' table.
