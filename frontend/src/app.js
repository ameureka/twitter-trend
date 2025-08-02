/**
 * 主应用程序文件
 * 整合所有组件，提供路由和状态管理
 */

class App {
    constructor() {
        this.currentView = 'dashboard';
        this.isInitialized = false;
        this.components = new Map();
        this.globalState = {
            user: null,
            apiKey: null,
            systemStatus: 'unknown',
            notifications: [],
            isOnline: navigator.onLine
        };
        this.eventBus = new EventTarget();
    }

    /**
     * 初始化应用程序
     */
    async init() {
        console.log('初始化应用程序...');
        
        try {
            // 显示全局加载状态
            this.showGlobalLoading(true);
            
            // 初始化基础功能
            await this.initializeBase();
            
            // 检查API连接
            await this.checkApiConnection();
            
            // 初始化组件
            await this.initializeComponents();
            
            // 设置路由
            this.setupRouting();
            
            // 设置全局事件监听
            this.setupGlobalEventListeners();
            
            // 启动系统状态监控
            this.startSystemMonitoring();
            
            // 加载初始视图
            await this.loadView(this.currentView);
            
            this.isInitialized = true;
            console.log('应用程序初始化完成');
            
        } catch (error) {
            console.error('应用程序初始化失败:', error);
            this.showError('应用程序初始化失败，请刷新页面重试');
        } finally {
            this.showGlobalLoading(false);
        }
    }

    /**
     * 初始化基础功能
     */
    async initializeBase() {
        // 初始化API密钥
        const savedApiKey = helpers.storage.get('api_key');
        if (savedApiKey) {
            api.setApiKey(savedApiKey);
            this.globalState.apiKey = savedApiKey;
        }
        
        // 初始化主题
        this.initializeTheme();
        
        // 初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * 初始化主题
     */
    initializeTheme() {
        const savedTheme = helpers.storage.get('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        // 更新主题切换按钮状态
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.checked = savedTheme === 'dark';
        }
    }

    /**
     * 检查API连接
     */
    async checkApiConnection() {
        try {
            const result = await api.checkConnection();
            
            if (result.success) {
                this.updateApiStatus(true);
                
                // 检查数据库状态
                if (result.data && result.data.database) {
                    const dbHealthy = result.data.database === 'healthy';
                    this.updateDatabaseStatus(dbHealthy);
                }
                
                console.log('API连接检查成功');
            } else {
                this.updateApiStatus(false);
                this.updateDatabaseStatus(false);
                console.warn('API连接失败，将使用模拟数据');
            }
        } catch (error) {
            console.error('API连接检查失败:', error);
            this.updateApiStatus(false);
            this.updateDatabaseStatus(false);
            console.warn('API连接失败，将使用模拟数据');
        }
    }

    /**
     * 初始化组件
     */
    async initializeComponents() {
        // 注册组件
        this.components.set('dashboard', window.dashboard);
        this.components.set('tasks', window.taskManager);
        this.components.set('projects', window.projectManager);
        this.components.set('analytics', window.analyticsManager);
        this.components.set('logs', window.logsManager);
        this.components.set('settings', window.settingsManager);
        
        // 注册组件类到全局对象（用于模板获取）
        if (window.dashboard && window.dashboard.constructor) {
            window.Dashboard = window.dashboard.constructor;
        }
        if (window.tasksManager && window.tasksManager.constructor) {
            window.TasksManager = window.tasksManager.constructor;
        }
        if (window.projectsManager && window.projectsManager.constructor) {
            window.ProjectsManager = window.projectsManager.constructor;
        }
        if (window.analyticsManager && window.analyticsManager.constructor) {
            window.AnalyticsManager = window.analyticsManager.constructor;
        }
        if (window.settingsManager && window.settingsManager.constructor) {
            window.SettingsManager = window.settingsManager.constructor;
        }
        
        // 初始化所有组件
        for (const [name, component] of this.components) {
            try {
                if (component && typeof component.init === 'function') {
                    console.log(`初始化组件: ${name}`);
                    await component.init();
                }
            } catch (error) {
                console.error(`组件 ${name} 初始化失败:`, error);
            }
        }
    }

    /**
     * 设置路由
     */
    setupRouting() {
        // 监听浏览器前进后退
        window.addEventListener('popstate', (e) => {
            const view = e.state?.view || 'dashboard';
            this.loadView(view, false);
        });
        
        // 设置导航链接点击事件
        document.addEventListener('click', (e) => {
            const navLink = e.target.closest('[data-view]');
            if (navLink) {
                e.preventDefault();
                const view = navLink.getAttribute('data-view');
                this.navigateTo(view);
            }
        });
        
        // 监听Alpine.js的导航事件
        document.addEventListener('alpine:init', () => {
            // 确保Alpine.js可以访问导航方法
            window.appNavigate = (view) => {
                this.navigateTo(view);
            };
        });
        
        // 从URL获取初始视图
        const urlParams = new URLSearchParams(window.location.search);
        const initialView = urlParams.get('view') || 'dashboard';
        this.currentView = initialView;
    }

    /**
     * 导航到指定视图
     * @param {string} view - 视图名称
     */
    async navigateTo(view) {
        if (view === this.currentView) return;
        
        try {
            await this.loadView(view);
            
            // 更新URL
            const url = new URL(window.location);
            url.searchParams.set('view', view);
            window.history.pushState({ view }, '', url);
            
        } catch (error) {
            console.error(`导航到 ${view} 失败:`, error);
            this.showError(`加载页面失败: ${error.message}`);
        }
    }

    /**
     * 加载视图
     * @param {string} view - 视图名称
     * @param {boolean} updateHistory - 是否更新历史记录
     */
    async loadView(view, updateHistory = true) {
        console.log(`加载视图: ${view}`);
        
        try {
            // 更新导航状态
            this.updateNavigation(view);
            
            // 获取主内容区域
            const mainContent = document.getElementById('main-content');
            if (!mainContent) {
                throw new Error('主内容区域未找到');
            }
            
            // 显示加载状态
            mainContent.innerHTML = this.getLoadingTemplate();
            
            // 获取视图模板
            const template = this.getViewTemplate(view);
            
            // 渲染视图
            mainContent.innerHTML = template;
            
            // 重新初始化图标
            if (window.lucide) {
                window.lucide.createIcons();
            }
            
            // 渲染视图内容
            const component = this.components.get(view);
            if (component && typeof component.render === 'function') {
                await component.render();
            }
            
            this.currentView = view;
            
            // 触发视图加载事件
            this.eventBus.dispatchEvent(new CustomEvent('viewLoaded', {
                detail: { view }
            }));
            
        } catch (error) {
            console.error(`加载视图 ${view} 失败:`, error);
            throw error;
        }
    }

    /**
     * 更新导航状态
     * @param {string} activeView - 当前活动视图
     */
    updateNavigation(activeView) {
        const navLinks = document.querySelectorAll('[data-view]');
        navLinks.forEach(link => {
            const view = link.getAttribute('data-view');
            if (view === activeView) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    /**
     * 获取视图模板
     * @param {string} view - 视图名称
     * @returns {string} HTML模板
     */
    getViewTemplate(view) {
        const templates = {
            dashboard: window.dashboard?.constructor?.getTemplate?.() || this.getDefaultTemplate('仪表板'),
            tasks: window.taskManager?.constructor?.getTemplate?.() || this.getDefaultTemplate('任务管理'),
            projects: window.projectManager?.constructor?.getTemplate?.() || this.getDefaultTemplate('项目管理'),
            analytics: window.analyticsManager?.constructor?.getTemplate?.() || this.getDefaultTemplate('数据分析'),
            logs: window.logsManager?.constructor?.getTemplate?.() || this.getDefaultTemplate('日志管理'),
            settings: window.settingsManager?.constructor?.getTemplate?.() || this.getDefaultTemplate('系统设置')
        };
        
        return templates[view] || this.getDefaultTemplate('页面未找到');
    }

    /**
     * 获取默认模板
     * @param {string} title - 页面标题
     * @returns {string} HTML模板
     */
    getDefaultTemplate(title) {
        return `
            <div class="text-center py-12">
                <div class="mb-4">
                    <i data-lucide="alert-circle" class="w-16 h-16 mx-auto text-gray-400"></i>
                </div>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">${title}</h2>
                <p class="text-gray-600">该页面正在开发中...</p>
            </div>
        `;
    }

    /**
     * 获取加载模板
     * @returns {string} HTML模板
     */
    getLoadingTemplate() {
        return `
            <div class="text-center py-12">
                <div class="loading-dots mb-4">
                    <span style="--i: 0"></span>
                    <span style="--i: 1"></span>
                    <span style="--i: 2"></span>
                </div>
                <p class="text-gray-600">加载中...</p>
            </div>
        `;
    }

    /**
     * 设置全局事件监听
     */
    setupGlobalEventListeners() {
        // 网络状态监听
        window.addEventListener('online', () => {
            this.globalState.isOnline = true;
            this.updateOnlineStatus(true);
            this.checkApiConnection();
        });
        
        window.addEventListener('offline', () => {
            this.globalState.isOnline = false;
            this.updateOnlineStatus(false);
        });
        
        // 主题切换
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('change', (e) => {
                this.toggleTheme(e.target.checked);
            });
        }
        
        // 刷新按钮
        const refreshBtn = document.getElementById('global-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshCurrentView();
            });
        }
        
        // 通知中心
        const notificationBtn = document.getElementById('notification-center');
        if (notificationBtn) {
            notificationBtn.addEventListener('click', () => {
                this.toggleNotificationCenter();
            });
        }
        
        // 键盘快捷键
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
        
        // 全局错误处理
        window.addEventListener('error', (e) => {
            console.error('全局错误:', e.error);
            this.showError('发生未知错误，请刷新页面');
        });
        
        window.addEventListener('unhandledrejection', (e) => {
            console.error('未处理的Promise拒绝:', e.reason);
            this.showError('操作失败，请重试');
        });
    }

    /**
     * 处理键盘快捷键
     * @param {KeyboardEvent} e - 键盘事件
     */
    handleKeyboardShortcuts(e) {
        // Ctrl/Cmd + R: 刷新当前视图
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            this.refreshCurrentView();
        }
        
        // Ctrl/Cmd + 1-5: 快速导航
        if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '5') {
            e.preventDefault();
            const views = ['dashboard', 'tasks', 'projects', 'analytics', 'settings'];
            const viewIndex = parseInt(e.key) - 1;
            if (views[viewIndex]) {
                this.navigateTo(views[viewIndex]);
            }
        }
    }

    /**
     * 切换主题
     * @param {boolean} isDark - 是否为深色主题
     */
    toggleTheme(isDark) {
        const theme = isDark ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', theme);
        helpers.storage.set('theme', theme);
        
        // 触发主题变更事件
        this.eventBus.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme }
        }));
    }

    /**
     * 刷新当前视图
     */
    async refreshCurrentView() {
        try {
            const component = this.components.get(this.currentView);
            if (component && typeof component.init === 'function') {
                await component.init();
            }
            this.showSuccess('页面已刷新');
        } catch (error) {
            console.error('刷新视图失败:', error);
            this.showError('刷新失败，请重试');
        }
    }

    /**
     * 切换通知中心
     */
    toggleNotificationCenter() {
        const notificationPanel = document.getElementById('notification-panel');
        if (notificationPanel) {
            const isVisible = notificationPanel.style.display !== 'none';
            notificationPanel.style.display = isVisible ? 'none' : 'block';
        }
    }

    /**
     * 启动系统监控
     */
    startSystemMonitoring() {
        // 每30秒检查一次系统状态
        setInterval(async () => {
            try {
                const result = await api.getSystemHealth();
                if (result.success) {
                    this.updateSystemStatus('online');
                } else {
                    this.updateSystemStatus('warning');
                }
            } catch (error) {
                this.updateSystemStatus('offline');
            }
        }, 30000);
    }

    /**
     * 更新系统状态
     * @param {string} status - 状态 (online, offline, warning)
     */
    updateSystemStatus(status) {
        this.globalState.systemStatus = status;
        
        // 更新Alpine.js的systemHealth对象
        if (window.Alpine && window.Alpine.store) {
            const store = window.Alpine.store('app');
            if (store && store.systemHealth) {
                store.systemHealth.status = status === 'online' ? 'healthy' : 'unhealthy';
                store.systemHealth.api_status = status === 'online' ? 'connected' : 'disconnected';
            }
        }
        
        const statusElement = document.getElementById('system-status');
        if (statusElement) {
            statusElement.className = `status-indicator status-${status}`;
            
            const statusText = {
                online: '在线',
                offline: '离线',
                warning: '警告'
            };
            
            statusElement.title = `系统状态: ${statusText[status] || '未知'}`;
        }
    }

    /**
     * 更新API连接状态
     * @param {boolean} connected - 是否连接
     */
    updateApiStatus(connected) {
        console.log('updateApiStatus被调用，参数:', connected);
        
        this.globalState.apiConnected = connected;
        console.log('globalState.apiConnected已更新为:', connected);
        
        try {
            // 直接访问Alpine数据栈
            const bodyElement = document.body;
            if (bodyElement._x_dataStack && bodyElement._x_dataStack.length > 0) {
                const alpineData = bodyElement._x_dataStack[0];
                
                if (alpineData && alpineData.systemHealth) {
                    console.log('更新前api_status:', alpineData.systemHealth.api_status);
                    alpineData.systemHealth.api_status = connected ? 'connected' : 'disconnected';
                    console.log('更新后api_status:', alpineData.systemHealth.api_status);
                    
                    // 调用整体状态更新
                    this.updateOverallSystemStatus();
                    
                    // 触发Alpine.js重新渲染
                    if (window.Alpine) {
                        window.Alpine.nextTick(() => {
                            console.log('Alpine.js重新渲染完成');
                        });
                    }
                } else {
                    console.warn('Alpine.js systemHealth对象未找到');
                }
            } else {
                console.warn('Alpine.js未找到或未初始化');
            }
        } catch (error) {
            console.error('更新API状态失败:', error);
        }
    }

    /**
     * 更新数据库连接状态
     * @param {boolean} connected - 是否连接
     */
    updateDatabaseStatus(connected) {
        console.log('updateDatabaseStatus被调用，参数:', connected);
        
        this.globalState.databaseConnected = connected;
        console.log('globalState.databaseConnected已更新为:', connected);
        
        try {
            // 直接访问Alpine数据栈
            const bodyElement = document.body;
            if (bodyElement._x_dataStack && bodyElement._x_dataStack.length > 0) {
                const alpineData = bodyElement._x_dataStack[0];
                
                if (alpineData && alpineData.systemHealth) {
                    console.log('更新前database_status:', alpineData.systemHealth.database_status);
                    alpineData.systemHealth.database_status = connected ? 'connected' : 'disconnected';
                    console.log('更新后database_status:', alpineData.systemHealth.database_status);
                    
                    // 调用整体状态更新
                    this.updateOverallSystemStatus();
                    
                    // 触发Alpine.js重新渲染
                    if (window.Alpine) {
                        window.Alpine.nextTick(() => {
                            console.log('Alpine.js重新渲染完成');
                        });
                    }
                } else {
                    console.warn('Alpine.js systemHealth对象未找到');
                }
            } else {
                console.warn('Alpine.js未找到或未初始化');
            }
        } catch (error) {
            console.error('更新数据库状态失败:', error);
        }
    }

    /**
     * 更新整体系统状态
     */
    updateOverallSystemStatus() {
        console.log('updateOverallSystemStatus被调用');
        
        try {
            // 直接访问Alpine数据栈
            const bodyElement = document.body;
            if (bodyElement._x_dataStack && bodyElement._x_dataStack.length > 0) {
                const alpineData = bodyElement._x_dataStack[0];
                
                if (alpineData && alpineData.systemHealth) {
                    console.log('更新前overall status:', alpineData.systemHealth.status);
                    
                    const isHealthy = alpineData.systemHealth.api_status === 'connected' && 
                                    alpineData.systemHealth.database_status === 'connected';
                    alpineData.systemHealth.status = isHealthy ? 'healthy' : 'unhealthy';
                    console.log('更新后overall status:', alpineData.systemHealth.status);
                    
                    // 触发Alpine.js重新渲染
                    if (window.Alpine) {
                        window.Alpine.nextTick(() => {
                            console.log('Alpine.js重新渲染完成');
                        });
                    }
                } else {
                    console.warn('Alpine.js systemHealth对象未找到');
                }
            } else {
                console.warn('Alpine.js未找到或未初始化');
            }
        } catch (error) {
            console.error('更新整体系统状态失败:', error);
        }
    }

    /**
     * 更新在线状态
     * @param {boolean} isOnline - 是否在线
     */
    updateOnlineStatus(isOnline) {
        const offlineIndicator = document.getElementById('offline-indicator');
        if (offlineIndicator) {
            offlineIndicator.style.display = isOnline ? 'none' : 'block';
        }
    }

    /**
     * 显示全局加载状态
     * @param {boolean} show - 是否显示
     */
    showGlobalLoading(show) {
        const loadingElement = document.getElementById('global-loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'flex' : 'none';
        }
    }

    /**
     * 添加通知
     * @param {Object} notification - 通知对象
     */
    addNotification(notification) {
        const id = Date.now().toString();
        const notificationWithId = {
            id,
            timestamp: new Date(),
            ...notification
        };
        
        this.globalState.notifications.unshift(notificationWithId);
        
        // 限制通知数量
        if (this.globalState.notifications.length > 50) {
            this.globalState.notifications = this.globalState.notifications.slice(0, 50);
        }
        
        this.updateNotificationBadge();
        
        // 如果是错误或警告，显示弹窗
        if (notification.type === 'error' || notification.type === 'warning') {
            this.showToast(notification);
        }
    }

    /**
     * 更新通知徽章
     */
    updateNotificationBadge() {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            const unreadCount = this.globalState.notifications.filter(n => !n.read).length;
            if (unreadCount > 0) {
                badge.textContent = unreadCount > 99 ? '99+' : unreadCount.toString();
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    /**
     * 显示Toast通知
     * @param {Object} notification - 通知对象
     */
    showToast(notification) {
        // 这里可以实现Toast通知显示逻辑
        console.log('Toast通知:', notification);
    }

    /**
     * 显示错误信息
     * @param {string} message - 错误信息
     */
    showError(message) {
        this.addNotification({
            type: 'error',
            title: '错误',
            message,
            read: false
        });
    }

    /**
     * 显示成功信息
     * @param {string} message - 成功信息
     */
    showSuccess(message) {
        this.addNotification({
            type: 'success',
            title: '成功',
            message,
            read: false
        });
    }

    /**
     * 显示警告信息
     * @param {string} message - 警告信息
     */
    showWarning(message) {
        this.addNotification({
            type: 'warning',
            title: '警告',
            message,
            read: false
        });
    }

    /**
     * 显示信息
     * @param {string} message - 信息内容
     */
    showInfo(message) {
        this.addNotification({
            type: 'info',
            title: '信息',
            message,
            read: false
        });
    }

    /**
     * 获取全局状态
     * @returns {Object} 全局状态
     */
    getGlobalState() {
        return this.globalState;
    }

    /**
     * 更新全局状态
     * @param {Object} updates - 状态更新
     */
    updateGlobalState(updates) {
        Object.assign(this.globalState, updates);
        
        // 触发状态变更事件
        this.eventBus.dispatchEvent(new CustomEvent('stateChanged', {
            detail: { updates }
        }));
    }

    /**
     * 订阅事件
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数
     */
    on(event, callback) {
        this.eventBus.addEventListener(event, callback);
    }

    /**
     * 取消订阅事件
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数
     */
    off(event, callback) {
        this.eventBus.removeEventListener(event, callback);
    }

    /**
     * 触发事件
     * @param {string} event - 事件名称
     * @param {*} detail - 事件详情
     */
    emit(event, detail) {
        this.eventBus.dispatchEvent(new CustomEvent(event, { detail }));
    }

    /**
     * 清理资源
     */
    cleanup() {
        // 清理组件
        for (const [name, component] of this.components) {
            if (component && typeof component.cleanup === 'function') {
                component.cleanup();
            }
        }
        
        // 清理事件监听器
        this.eventBus.removeEventListener();
    }
}

// 创建全局应用实例
const app = new App();

// 导出到全局
window.app = app;

// 延迟初始化，等待Alpine.js调用
// 不自动初始化，由Alpine.js的initApp()方法调用

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = app;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return app;
    });
}