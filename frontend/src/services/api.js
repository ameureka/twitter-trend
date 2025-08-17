/**
 * API服务模块
 * 提供与后端API交互的核心功能
 */

class APIService {
    constructor() {
        // 使用当前页面的origin作为API基础URL，如果是8080端口则指向8050
        const currentPort = window.location.port;
        if (currentPort === '8080') {
            // 开发环境，前端在8080，API在8050
            this.baseURL = window.location.protocol + '//' + window.location.hostname + ':8050';
        } else {
            // 生产环境或其他情况
            this.baseURL = window.location.origin;
        }
        this.apiKey = localStorage.getItem('api_key') || 'dev-api-key-12345'; // 开发环境默认API密钥
        this.defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
    }

    /**
     * 设置API密钥
     * @param {string} apiKey - API密钥
     */
    setApiKey(apiKey) {
        this.apiKey = apiKey;
        localStorage.setItem('api_key', apiKey);
    }

    /**
     * 获取请求头
     * @param {Object} additionalHeaders - 额外的请求头
     * @returns {Object} 完整的请求头
     */
    getHeaders(additionalHeaders = {}) {
        const headers = { ...this.defaultHeaders, ...additionalHeaders };
        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }
        return headers;
    }

    /**
     * 发送HTTP请求
     * @param {string} endpoint - API端点
     * @param {Object} options - 请求选项
     * @returns {Promise} 请求结果
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: this.getHeaders(options.headers),
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            // 处理非JSON响应
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                if (response.ok) {
                    return { success: true, data: await response.text() };
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP ${response.status}: ${response.statusText}`);
            }

            return { success: true, data };
        } catch (error) {
            console.error('API请求失败:', error);
            return { 
                success: false, 
                error: error.message || '网络请求失败',
                status: error.status || 0
            };
        }
    }

    /**
     * GET请求
     * @param {string} endpoint - API端点
     * @param {Object} params - 查询参数
     * @returns {Promise} 请求结果
     */
    async get(endpoint, params = {}) {
        let finalEndpoint = endpoint;
        
        if (Object.keys(params).length > 0) {
            const url = new URL(`${this.baseURL}${endpoint}`);
            Object.keys(params).forEach(key => {
                if (params[key] !== undefined && params[key] !== null) {
                    url.searchParams.append(key, params[key]);
                }
            });
            finalEndpoint = url.pathname + url.search;
        }
        
        return this.request(finalEndpoint, {
            method: 'GET'
        });
    }

    /**
     * POST请求
     * @param {string} endpoint - API端点
     * @param {Object} data - 请求数据
     * @returns {Promise} 请求结果
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT请求
     * @param {string} endpoint - API端点
     * @param {Object} data - 请求数据
     * @returns {Promise} 请求结果
     */
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE请求
     * @param {string} endpoint - API端点
     * @returns {Promise} 请求结果
     */
    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }

    // ==================== 连接检查 ====================

    /**
     * 检查API连接
     * @returns {Promise} 连接状态
     */
    async checkConnection() {
        return this.get('/api/health');
    }

    // ==================== 认证相关 ====================

    /**
     * 验证API密钥
     * @param {string} apiKey - API密钥
     * @returns {Promise} 验证结果
     */
    async verifyApiKey(apiKey) {
        const tempApiKey = this.apiKey;
        this.apiKey = apiKey;
        
        const result = await this.get('/api/auth/verify');
        
        if (result.success) {
            this.setApiKey(apiKey);
        } else {
            this.apiKey = tempApiKey;
        }
        
        return result;
    }

    /**
     * 获取当前用户信息
     * @returns {Promise} 用户信息
     */
    async getCurrentUser() {
        return this.get('/api/auth/me');
    }

    /**
     * 获取用户权限
     * @returns {Promise} 权限信息
     */
    async getUserPermissions() {
        return this.get('/api/auth/permissions');
    }

    // ==================== 仪表板相关 ====================

    /**
     * 获取仪表板统计数据
     * @returns {Promise} 统计数据
     */
    async getDashboardStats() {
        return this.get('/api/dashboard/stats/');
    }

    /**
     * 获取系统健康状态
     * @returns {Promise} 健康状态
     */
    async getSystemHealth() {
        return this.get('/api/dashboard/health/');
    }

    /**
     * 获取最近活动
     * @param {number} limit - 限制数量
     * @returns {Promise} 最近活动
     */
    async getRecentActivity(limit = 10) {
        return this.get('/api/dashboard/recent-activity/', { limit });
    }

    /**
     * 获取快速统计
     * @returns {Promise} 快速统计
     */
    async getQuickStats() {
        return this.get('/api/dashboard/quick-stats/');
    }

    // ==================== 任务管理 ====================

    /**
     * 获取任务列表
     * @param {Object} params - 查询参数
     * @returns {Promise} 任务列表
     */
    async getTasks(params = {}) {
        const defaultParams = {
            page: 1,
            size: 20,
            status: null,
            project_id: null,
            search: null
        };
        return this.get('/api/tasks/', { ...defaultParams, ...params });
    }

    /**
     * 获取任务详情
     * @param {number} taskId - 任务ID
     * @returns {Promise} 任务详情
     */
    async getTask(taskId) {
        return this.get(`/api/tasks/${taskId}`);
    }

    /**
     * 创建任务
     * @param {Object} taskData - 任务数据
     * @returns {Promise} 创建结果
     */
    async createTask(taskData) {
        return this.post('/api/tasks/', taskData);
    }

    /**
     * 更新任务
     * @param {number} taskId - 任务ID
     * @param {Object} taskData - 任务数据
     * @returns {Promise} 更新结果
     */
    async updateTask(taskId, taskData) {
        return this.put(`/api/tasks/${taskId}`, taskData);
    }

    /**
     * 删除任务
     * @param {number} taskId - 任务ID
     * @returns {Promise} 删除结果
     */
    async deleteTask(taskId) {
        return this.delete(`/api/tasks/${taskId}`);
    }

    /**
     * 执行任务
     * @param {number} taskId - 任务ID
     * @returns {Promise} 执行结果
     */
    async executeTask(taskId) {
        return this.post(`/api/tasks/${taskId}/execute`);
    }

    /**
     * 取消任务
     * @param {number} taskId - 任务ID
     * @returns {Promise} 取消结果
     */
    async cancelTask(taskId) {
        return this.post(`/api/tasks/${taskId}/cancel`);
    }

    /**
     * 批量操作任务
     * @param {Object} actionData - 操作数据
     * @returns {Promise} 操作结果
     */
    async bulkTaskAction(actionData) {
        return this.post('/api/tasks/bulk-action', actionData);
    }

    /**
     * 获取任务日志
     * @param {number} taskId - 任务ID
     * @param {Object} params - 查询参数
     * @returns {Promise} 任务日志
     */
    async getTaskLogs(taskId, params = {}) {
        return this.get(`/api/tasks/${taskId}/logs`, params);
    }

    // ==================== 项目管理 ====================

    /**
     * 获取项目列表
     * @param {Object} params - 查询参数
     * @returns {Promise} 项目列表
     */
    async getProjects(params = {}) {
        const defaultParams = {
            page: 1,
            size: 20,
            search: null
        };
        return this.get('/api/projects/', { ...defaultParams, ...params });
    }

    /**
     * 获取项目详情
     * @param {number} projectId - 项目ID
     * @returns {Promise} 项目详情
     */
    async getProject(projectId) {
        return this.get(`/api/projects/${projectId}`);
    }

    /**
     * 创建项目
     * @param {Object} projectData - 项目数据
     * @returns {Promise} 创建结果
     */
    async createProject(projectData) {
        return this.post('/api/projects/', projectData);
    }

    /**
     * 更新项目
     * @param {number} projectId - 项目ID
     * @param {Object} projectData - 项目数据
     * @returns {Promise} 更新结果
     */
    async updateProject(projectId, projectData) {
        return this.put(`/api/projects/${projectId}`, projectData);
    }

    /**
     * 删除项目
     * @param {number} projectId - 项目ID
     * @returns {Promise} 删除结果
     */
    async deleteProject(projectId) {
        return this.delete(`/api/projects/${projectId}`);
    }

    /**
     * 扫描项目
     * @param {number} projectId - 项目ID
     * @returns {Promise} 扫描结果
     */
    async scanProject(projectId) {
        return this.post(`/api/projects/${projectId}/scan`);
    }

    /**
     * 获取项目任务
     * @param {number} projectId - 项目ID
     * @param {Object} params - 查询参数
     * @returns {Promise} 项目任务
     */
    async getProjectTasks(projectId, params = {}) {
        return this.get(`/api/projects/${projectId}/tasks`, params);
    }

    /**
     * 获取项目设置
     * @param {number} projectId - 项目ID
     * @returns {Promise} 项目设置
     */
    async getProjectSettings(projectId) {
        return this.get(`/api/projects/${projectId}/settings`);
    }

    /**
     * 更新项目设置
     * @param {number} projectId - 项目ID
     * @param {Object} settings - 设置数据
     * @returns {Promise} 更新结果
     */
    async updateProjectSettings(projectId, settings) {
        return this.put(`/api/projects/${projectId}/settings`, settings);
    }

    /**
     * 获取项目内容源
     * @param {number} projectId - 项目ID
     * @returns {Promise} 内容源列表
     */
    async getProjectSources(projectId) {
        return this.get(`/api/projects/${projectId}/sources`);
    }

    /**
     * 获取项目分析数据
     * @param {number} projectId - 项目ID
     * @returns {Promise} 分析数据
     */
    async getProjectAnalytics(projectId) {
        return this.get(`/api/projects/${projectId}/analytics`);
    }

    // ==================== 系统管理 ====================

    /**
     * 获取系统信息
     * @returns {Promise} 系统信息
     */
    async getSystemInfo() {
        return this.get('/api/system/info/');
    }

    /**
     * 重启系统
     * @returns {Promise} 重启结果
     */
    async restartSystem() {
        return this.post('/api/system/restart/');
    }

    /**
     * 初始化数据库
     * @returns {Promise} 初始化结果
     */
    async initializeDatabase() {
        return this.post('/api/database/initialize');
    }

    /**
     * 清理数据库
     * @returns {Promise} 清理结果
     */
    async cleanDatabase() {
        return this.post('/api/database/clean');
    }

    /**
     * 备份数据库
     * @returns {Promise} 备份结果
     */
    async backupDatabase() {
        return this.post('/api/database/backup');
    }

    /**
     * 获取数据库统计
     * @returns {Promise} 数据库统计
     */
    async getDatabaseStats() {
        return this.get('/api/database/stats');
    }

    // ==================== 调度器管理 ====================

    /**
     * 启动调度器
     * @returns {Promise} 启动结果
     */
    async startScheduler() {
        return this.post('/api/scheduler/start');
    }

    /**
     * 停止调度器
     * @returns {Promise} 停止结果
     */
    async stopScheduler() {
        return this.post('/api/scheduler/stop');
    }

    /**
     * 重启调度器
     * @returns {Promise} 重启结果
     */
    async restartScheduler() {
        return this.post('/api/scheduler/restart');
    }

    /**
     * 获取调度器状态
     * @returns {Promise} 调度器状态
     */
    async getSchedulerStatus() {
        return this.get('/api/scheduler/status');
    }

    /**
     * 获取调度器统计
     * @returns {Promise} 调度器统计
     */
    async getSchedulerStats() {
        return this.get('/api/scheduler/stats');
    }

    // ==================== 配置管理 ====================

    /**
     * 获取配置
     * @returns {Promise} 配置信息
     */
    async getConfig() {
        return this.get('/api/config/');
    }

    /**
     * 更新配置
     * @param {Object} config - 配置数据
     * @returns {Promise} 更新结果
     */
    async updateConfig(config) {
        return this.put('/api/config/', config);
    }

    /**
     * 重载配置
     * @returns {Promise} 重载结果
     */
    async reloadConfig() {
        return this.post('/api/config/reload');
    }

    /**
     * 获取配置信息
     * @returns {Promise} 配置信息
     */
    async getConfigInfo() {
        return this.get('/api/config/info');
    }

    // ==================== 性能监控 ====================

    /**
     * 获取性能指标
     * @returns {Promise} 性能指标
     */
    async getPerformanceMetrics() {
        return this.get('/api/performance/metrics');
    }

    /**
     * 获取性能警报
     * @returns {Promise} 性能警报
     */
    async getPerformanceAlerts() {
        return this.get('/api/performance/alerts');
    }

    /**
     * 获取健康检查
     * @returns {Promise} 健康检查
     */
    async getHealthCheck() {
        return this.get('/api/performance/health');
    }

    // ==================== 错误管理 ====================

    /**
     * 获取错误统计
     * @returns {Promise} 错误统计
     */
    async getErrorStats() {
        return this.get('/api/errors/stats');
    }

    /**
     * 获取最近错误
     * @param {Object} params - 查询参数
     * @returns {Promise} 最近错误
     */
    async getRecentErrors(params = {}) {
        return this.get('/api/errors/recent', params);
    }

    /**
     * 解决错误
     * @param {number} errorId - 错误ID
     * @returns {Promise} 解决结果
     */
    async resolveError(errorId) {
        return this.post(`/api/errors/${errorId}/resolve`);
    }

    // ==================== 分析数据 ====================

    /**
     * 获取分析概览
     * @returns {Promise} 分析概览
     */
    async getAnalyticsOverview() {
        return this.get('/api/analytics/overview');
    }

    /**
     * 获取分析趋势
     * @param {Object} params - 查询参数
     * @returns {Promise} 分析趋势
     */
    async getAnalyticsTrends(params = {}) {
        return this.get('/api/analytics/trends', params);
    }

    /**
     * 获取性能分析
     * @param {Object} params - 查询参数
     * @returns {Promise} 性能分析
     */
    async getAnalyticsPerformance(params = {}) {
        return this.get('/api/analytics/performance', params);
    }

    /**
     * 获取系统配置
     * @returns {Promise} 系统配置
     */
    async getSystemConfig() {
        return this.get('/api/system/config');
    }

    // ==================== 工具方法 ====================

    /**
     * 获取API文档
     * @returns {Promise} API文档
     */
    async getApiDocs() {
        return this.get('/docs');
    }

    /**
     * 上传文件
     * @param {string} endpoint - 上传端点
     * @param {FormData} formData - 文件数据
     * @returns {Promise} 上传结果
     */
    async uploadFile(endpoint, formData) {
        return this.request(endpoint, {
            method: 'POST',
            body: formData,
            headers: {
                'X-API-Key': this.apiKey
            }
        });
    }

    /**
     * 下载文件
     * @param {string} endpoint - 下载端点
     * @returns {Promise} 文件数据
     */
    async downloadFile(endpoint) {
        const url = `${this.baseURL}${endpoint}`;
        const response = await fetch(url, {
            headers: this.getHeaders()
        });
        
        if (!response.ok) {
            throw new Error(`下载失败: ${response.statusText}`);
        }
        
        return response.blob();
    }
}

// 创建全局API实例
const api = new APIService();

// 导出API实例
window.api = api;

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return api;
    });
}