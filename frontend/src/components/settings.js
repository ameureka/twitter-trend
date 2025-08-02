/**
 * 系统设置组件
 * 提供系统配置和管理功能
 */

class SettingsManager {
    constructor() {
        this.currentTab = 'general';
        this.unsavedChanges = false;
        this.originalSettings = {};
        this.currentSettings = {};
    }

    /**
     * 初始化设置管理器
     */
    async init() {
        console.log('初始化系统设置管理器...');
        this.setupEventListeners();
        this.setupTabNavigation();
        await this.loadSettings();
    }

    async render() {
        console.log('渲染系统设置管理器...');
        this.renderSettings();
    }

    /**
     * 加载系统设置
     */
    async loadSettings() {
        this.showLoading(true);
        
        try {
            const result = await api.getSystemConfig();
            
            if (result.success) {
                this.originalSettings = helpers.deepClone(result.data);
                this.currentSettings = helpers.deepClone(result.data);
                this.renderSettings();
            } else {
                this.showError('加载设置失败: ' + result.error);
            }
        } catch (error) {
            console.error('加载系统设置失败:', error);
            this.showError('加载设置失败，请检查网络连接');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * 渲染设置界面
     */
    renderSettings() {
        this.renderGeneralSettings();
        this.renderSchedulerSettings();
        this.renderNotificationSettings();
        this.renderSecuritySettings();
        this.renderAdvancedSettings();
        this.updateSaveButtonState();
    }

    /**
     * 渲染通用设置
     */
    renderGeneralSettings() {
        const container = document.getElementById('general-settings');
        if (!container) return;
        
        const settings = this.currentSettings.general || {};
        
        container.innerHTML = `
            <div class="space-y-6">
                <div class="form-group">
                    <label class="form-label">系统名称</label>
                    <input type="text" id="system-name" class="form-input" 
                           value="${settings.system_name || ''}" 
                           placeholder="输入系统名称">
                    <p class="form-help">显示在页面标题和导航栏中的系统名称</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">系统描述</label>
                    <textarea id="system-description" class="form-textarea" rows="3" 
                              placeholder="输入系统描述">${settings.system_description || ''}</textarea>
                    <p class="form-help">系统的简要描述信息</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">默认语言</label>
                    <select id="default-language" class="form-select">
                        <option value="zh-CN" ${settings.default_language === 'zh-CN' ? 'selected' : ''}>简体中文</option>
                        <option value="en-US" ${settings.default_language === 'en-US' ? 'selected' : ''}>English</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">时区设置</label>
                    <select id="timezone" class="form-select">
                        <option value="Asia/Shanghai" ${settings.timezone === 'Asia/Shanghai' ? 'selected' : ''}>Asia/Shanghai (UTC+8)</option>
                        <option value="UTC" ${settings.timezone === 'UTC' ? 'selected' : ''}>UTC (UTC+0)</option>
                        <option value="America/New_York" ${settings.timezone === 'America/New_York' ? 'selected' : ''}>America/New_York (UTC-5)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">日期格式</label>
                    <select id="date-format" class="form-select">
                        <option value="YYYY-MM-DD" ${settings.date_format === 'YYYY-MM-DD' ? 'selected' : ''}>YYYY-MM-DD</option>
                        <option value="MM/DD/YYYY" ${settings.date_format === 'MM/DD/YYYY' ? 'selected' : ''}>MM/DD/YYYY</option>
                        <option value="DD/MM/YYYY" ${settings.date_format === 'DD/MM/YYYY' ? 'selected' : ''}>DD/MM/YYYY</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="enable-dark-mode" 
                               ${settings.enable_dark_mode ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>启用深色模式</span>
                    </label>
                    <p class="form-help mt-2">为系统界面启用深色主题</p>
                </div>
            </div>
        `;
    }

    /**
     * 渲染调度器设置
     */
    renderSchedulerSettings() {
        const container = document.getElementById('scheduler-settings');
        if (!container) return;
        
        const settings = this.currentSettings.scheduler || {};
        
        container.innerHTML = `
            <div class="space-y-6">
                <div class="form-group">
                    <label class="form-label">最大并发任务数</label>
                    <input type="number" id="max-concurrent-tasks" class="form-input" 
                           value="${settings.max_concurrent_tasks || 10}" 
                           min="1" max="100">
                    <p class="form-help">同时执行的最大任务数量</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">任务超时时间 (秒)</label>
                    <input type="number" id="task-timeout" class="form-input" 
                           value="${settings.task_timeout || 300}" 
                           min="30" max="3600">
                    <p class="form-help">单个任务的最大执行时间</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">重试次数</label>
                    <input type="number" id="retry-attempts" class="form-input" 
                           value="${settings.retry_attempts || 3}" 
                           min="0" max="10">
                    <p class="form-help">任务失败时的重试次数</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">重试间隔 (秒)</label>
                    <input type="number" id="retry-delay" class="form-input" 
                           value="${settings.retry_delay || 60}" 
                           min="1" max="3600">
                    <p class="form-help">重试之间的等待时间</p>
                </div>
                
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="enable-scheduler" 
                               ${settings.enable_scheduler ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>启用任务调度器</span>
                    </label>
                    <p class="form-help mt-2">是否启用自动任务调度功能</p>
                </div>
                
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="auto-cleanup" 
                               ${settings.auto_cleanup ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>自动清理完成的任务</span>
                    </label>
                    <p class="form-help mt-2">自动删除超过指定时间的已完成任务</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">任务保留天数</label>
                    <input type="number" id="cleanup-days" class="form-input" 
                           value="${settings.cleanup_days || 30}" 
                           min="1" max="365">
                    <p class="form-help">已完成任务的保留天数</p>
                </div>
            </div>
        `;
    }

    /**
     * 渲染通知设置
     */
    renderNotificationSettings() {
        const container = document.getElementById('notification-settings');
        if (!container) return;
        
        const settings = this.currentSettings.notifications || {};
        
        container.innerHTML = `
            <div class="space-y-6">
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="enable-notifications" 
                               ${settings.enable_notifications ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>启用通知功能</span>
                    </label>
                    <p class="form-help mt-2">是否启用系统通知</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">邮件服务器 (SMTP)</label>
                    <input type="text" id="smtp-server" class="form-input" 
                           value="${settings.smtp_server || ''}" 
                           placeholder="smtp.example.com">
                </div>
                
                <div class="form-group">
                    <label class="form-label">SMTP 端口</label>
                    <input type="number" id="smtp-port" class="form-input" 
                           value="${settings.smtp_port || 587}" 
                           min="1" max="65535">
                </div>
                
                <div class="form-group">
                    <label class="form-label">发件人邮箱</label>
                    <input type="email" id="sender-email" class="form-input" 
                           value="${settings.sender_email || ''}" 
                           placeholder="noreply@example.com">
                </div>
                
                <div class="form-group">
                    <label class="form-label">邮箱密码</label>
                    <input type="password" id="email-password" class="form-input" 
                           value="${settings.email_password || ''}" 
                           placeholder="输入邮箱密码">
                </div>
                
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="use-tls" 
                               ${settings.use_tls ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>使用 TLS 加密</span>
                    </label>
                </div>
                
                <div class="form-group">
                    <label class="form-label">通知接收邮箱</label>
                    <textarea id="notification-emails" class="form-textarea" rows="3" 
                              placeholder="输入邮箱地址，每行一个">${(settings.notification_emails || []).join('\n')}</textarea>
                    <p class="form-help">接收系统通知的邮箱地址列表</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">通知类型</label>
                    <div class="space-y-2">
                        <label class="flex items-center space-x-2">
                            <input type="checkbox" id="notify-task-complete" 
                                   ${(settings.notification_types || []).includes('task_complete') ? 'checked' : ''}
                                   class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                            <span>任务完成</span>
                        </label>
                        <label class="flex items-center space-x-2">
                            <input type="checkbox" id="notify-task-failed" 
                                   ${(settings.notification_types || []).includes('task_failed') ? 'checked' : ''}
                                   class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                            <span>任务失败</span>
                        </label>
                        <label class="flex items-center space-x-2">
                            <input type="checkbox" id="notify-system-error" 
                                   ${(settings.notification_types || []).includes('system_error') ? 'checked' : ''}
                                   class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                            <span>系统错误</span>
                        </label>
                    </div>
                </div>
                
                <div class="form-group">
                    <button id="test-notification" class="btn btn-outline">
                        <i data-lucide="mail" class="w-4 h-4 mr-2"></i>
                        发送测试邮件
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 渲染安全设置
     */
    renderSecuritySettings() {
        const container = document.getElementById('security-settings');
        if (!container) return;
        
        const settings = this.currentSettings.security || {};
        
        container.innerHTML = `
            <div class="space-y-6">
                <div class="form-group">
                    <label class="form-label">API 密钥过期时间 (天)</label>
                    <input type="number" id="api-key-expiry" class="form-input" 
                           value="${settings.api_key_expiry || 365}" 
                           min="1" max="3650">
                    <p class="form-help">API 密钥的有效期</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">会话超时时间 (分钟)</label>
                    <input type="number" id="session-timeout" class="form-input" 
                           value="${settings.session_timeout || 60}" 
                           min="5" max="1440">
                    <p class="form-help">用户会话的超时时间</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">最大登录尝试次数</label>
                    <input type="number" id="max-login-attempts" class="form-input" 
                           value="${settings.max_login_attempts || 5}" 
                           min="1" max="20">
                    <p class="form-help">账户锁定前的最大登录失败次数</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">账户锁定时间 (分钟)</label>
                    <input type="number" id="lockout-duration" class="form-input" 
                           value="${settings.lockout_duration || 30}" 
                           min="1" max="1440">
                    <p class="form-help">账户被锁定的时间</p>
                </div>
                
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="enable-rate-limiting" 
                               ${settings.enable_rate_limiting ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>启用 API 速率限制</span>
                    </label>
                    <p class="form-help mt-2">限制 API 请求频率以防止滥用</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">速率限制 (请求/分钟)</label>
                    <input type="number" id="rate-limit" class="form-input" 
                           value="${settings.rate_limit || 100}" 
                           min="1" max="10000">
                    <p class="form-help">每分钟允许的最大请求数</p>
                </div>
                
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="enable-cors" 
                               ${settings.enable_cors ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>启用 CORS</span>
                    </label>
                    <p class="form-help mt-2">允许跨域请求</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">允许的域名</label>
                    <textarea id="allowed-origins" class="form-textarea" rows="3" 
                              placeholder="输入允许的域名，每行一个">${(settings.allowed_origins || []).join('\n')}</textarea>
                    <p class="form-help">允许访问 API 的域名列表</p>
                </div>
            </div>
        `;
    }

    /**
     * 渲染高级设置
     */
    renderAdvancedSettings() {
        const container = document.getElementById('advanced-settings');
        if (!container) return;
        
        const settings = this.currentSettings.advanced || {};
        
        container.innerHTML = `
            <div class="space-y-6">
                <div class="form-group">
                    <label class="form-label">日志级别</label>
                    <select id="log-level" class="form-select">
                        <option value="DEBUG" ${settings.log_level === 'DEBUG' ? 'selected' : ''}>DEBUG</option>
                        <option value="INFO" ${settings.log_level === 'INFO' ? 'selected' : ''}>INFO</option>
                        <option value="WARNING" ${settings.log_level === 'WARNING' ? 'selected' : ''}>WARNING</option>
                        <option value="ERROR" ${settings.log_level === 'ERROR' ? 'selected' : ''}>ERROR</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label class="form-label">日志保留天数</label>
                    <input type="number" id="log-retention-days" class="form-input" 
                           value="${settings.log_retention_days || 30}" 
                           min="1" max="365">
                    <p class="form-help">系统日志的保留天数</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">数据库连接池大小</label>
                    <input type="number" id="db-pool-size" class="form-input" 
                           value="${settings.db_pool_size || 10}" 
                           min="1" max="100">
                    <p class="form-help">数据库连接池的最大连接数</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">缓存过期时间 (秒)</label>
                    <input type="number" id="cache-expiry" class="form-input" 
                           value="${settings.cache_expiry || 3600}" 
                           min="60" max="86400">
                    <p class="form-help">缓存数据的过期时间</p>
                </div>
                
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="enable-debug-mode" 
                               ${settings.enable_debug_mode ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>启用调试模式</span>
                    </label>
                    <p class="form-help mt-2">启用详细的调试信息输出</p>
                </div>
                
                <div class="form-group">
                    <label class="flex items-center space-x-2">
                        <input type="checkbox" id="enable-metrics" 
                               ${settings.enable_metrics ? 'checked' : ''}
                               class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span>启用性能指标收集</span>
                    </label>
                    <p class="form-help mt-2">收集系统性能指标用于监控</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">备份间隔 (小时)</label>
                    <input type="number" id="backup-interval" class="form-input" 
                           value="${settings.backup_interval || 24}" 
                           min="1" max="168">
                    <p class="form-help">自动备份的时间间隔</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label">备份保留数量</label>
                    <input type="number" id="backup-retention" class="form-input" 
                           value="${settings.backup_retention || 7}" 
                           min="1" max="30">
                    <p class="form-help">保留的备份文件数量</p>
                </div>
            </div>
        `;
    }

    /**
     * 设置标签页导航
     */
    setupTabNavigation() {
        const tabButtons = document.querySelectorAll('[data-tab]');
        const tabContents = document.querySelectorAll('[data-tab-content]');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.getAttribute('data-tab');
                
                // 更新按钮状态
                tabButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                // 更新内容显示
                tabContents.forEach(content => {
                    if (content.getAttribute('data-tab-content') === tabId) {
                        content.style.display = 'block';
                    } else {
                        content.style.display = 'none';
                    }
                });
                
                this.currentTab = tabId;
            });
        });
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 保存按钮
        const saveBtn = document.getElementById('save-settings');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                this.saveSettings();
            });
        }

        // 重置按钮
        const resetBtn = document.getElementById('reset-settings');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.resetSettings();
            });
        }

        // 测试通知按钮
        document.addEventListener('click', (e) => {
            if (e.target.id === 'test-notification') {
                this.testNotification();
            }
        });

        // 监听表单变化
        document.addEventListener('input', (e) => {
            if (e.target.closest('.settings-container')) {
                this.markAsChanged();
            }
        });

        document.addEventListener('change', (e) => {
            if (e.target.closest('.settings-container')) {
                this.markAsChanged();
            }
        });

        // 页面离开前提醒
        window.addEventListener('beforeunload', (e) => {
            if (this.unsavedChanges) {
                e.preventDefault();
                e.returnValue = '您有未保存的更改，确定要离开吗？';
                return e.returnValue;
            }
        });
    }

    /**
     * 标记为已更改
     */
    markAsChanged() {
        this.unsavedChanges = true;
        this.updateSaveButtonState();
    }

    /**
     * 更新保存按钮状态
     */
    updateSaveButtonState() {
        const saveBtn = document.getElementById('save-settings');
        if (saveBtn) {
            saveBtn.disabled = !this.unsavedChanges;
            if (this.unsavedChanges) {
                saveBtn.classList.add('btn-primary');
                saveBtn.classList.remove('btn-outline');
            } else {
                saveBtn.classList.remove('btn-primary');
                saveBtn.classList.add('btn-outline');
            }
        }
    }

    /**
     * 收集当前设置
     */
    collectCurrentSettings() {
        const settings = {
            general: {
                system_name: document.getElementById('system-name')?.value || '',
                system_description: document.getElementById('system-description')?.value || '',
                default_language: document.getElementById('default-language')?.value || 'zh-CN',
                timezone: document.getElementById('timezone')?.value || 'Asia/Shanghai',
                date_format: document.getElementById('date-format')?.value || 'YYYY-MM-DD',
                enable_dark_mode: document.getElementById('enable-dark-mode')?.checked || false
            },
            scheduler: {
                max_concurrent_tasks: parseInt(document.getElementById('max-concurrent-tasks')?.value) || 10,
                task_timeout: parseInt(document.getElementById('task-timeout')?.value) || 300,
                retry_attempts: parseInt(document.getElementById('retry-attempts')?.value) || 3,
                retry_delay: parseInt(document.getElementById('retry-delay')?.value) || 60,
                enable_scheduler: document.getElementById('enable-scheduler')?.checked || false,
                auto_cleanup: document.getElementById('auto-cleanup')?.checked || false,
                cleanup_days: parseInt(document.getElementById('cleanup-days')?.value) || 30
            },
            notifications: {
                enable_notifications: document.getElementById('enable-notifications')?.checked || false,
                smtp_server: document.getElementById('smtp-server')?.value || '',
                smtp_port: parseInt(document.getElementById('smtp-port')?.value) || 587,
                sender_email: document.getElementById('sender-email')?.value || '',
                email_password: document.getElementById('email-password')?.value || '',
                use_tls: document.getElementById('use-tls')?.checked || false,
                notification_emails: document.getElementById('notification-emails')?.value.split('\n').filter(email => email.trim()),
                notification_types: [
                    ...(document.getElementById('notify-task-complete')?.checked ? ['task_complete'] : []),
                    ...(document.getElementById('notify-task-failed')?.checked ? ['task_failed'] : []),
                    ...(document.getElementById('notify-system-error')?.checked ? ['system_error'] : [])
                ]
            },
            security: {
                api_key_expiry: parseInt(document.getElementById('api-key-expiry')?.value) || 365,
                session_timeout: parseInt(document.getElementById('session-timeout')?.value) || 60,
                max_login_attempts: parseInt(document.getElementById('max-login-attempts')?.value) || 5,
                lockout_duration: parseInt(document.getElementById('lockout-duration')?.value) || 30,
                enable_rate_limiting: document.getElementById('enable-rate-limiting')?.checked || false,
                rate_limit: parseInt(document.getElementById('rate-limit')?.value) || 100,
                enable_cors: document.getElementById('enable-cors')?.checked || false,
                allowed_origins: document.getElementById('allowed-origins')?.value.split('\n').filter(origin => origin.trim())
            },
            advanced: {
                log_level: document.getElementById('log-level')?.value || 'INFO',
                log_retention_days: parseInt(document.getElementById('log-retention-days')?.value) || 30,
                db_pool_size: parseInt(document.getElementById('db-pool-size')?.value) || 10,
                cache_expiry: parseInt(document.getElementById('cache-expiry')?.value) || 3600,
                enable_debug_mode: document.getElementById('enable-debug-mode')?.checked || false,
                enable_metrics: document.getElementById('enable-metrics')?.checked || false,
                backup_interval: parseInt(document.getElementById('backup-interval')?.value) || 24,
                backup_retention: parseInt(document.getElementById('backup-retention')?.value) || 7
            }
        };
        
        return settings;
    }

    /**
     * 保存设置
     */
    async saveSettings() {
        try {
            const settings = this.collectCurrentSettings();
            
            const result = await api.updateSystemConfig(settings);
            
            if (result.success) {
                this.originalSettings = helpers.deepClone(settings);
                this.currentSettings = helpers.deepClone(settings);
                this.unsavedChanges = false;
                this.updateSaveButtonState();
                this.showSuccess('设置保存成功');
            } else {
                this.showError('保存设置失败: ' + result.error);
            }
        } catch (error) {
            console.error('保存设置失败:', error);
            this.showError('保存设置失败，请重试');
        }
    }

    /**
     * 重置设置
     */
    resetSettings() {
        if (this.unsavedChanges) {
            if (!confirm('确定要重置所有更改吗？未保存的更改将丢失。')) {
                return;
            }
        }
        
        this.currentSettings = helpers.deepClone(this.originalSettings);
        this.renderSettings();
        this.unsavedChanges = false;
        this.updateSaveButtonState();
        this.showSuccess('设置已重置');
    }

    /**
     * 测试通知
     */
    async testNotification() {
        try {
            const result = await api.testNotification();
            
            if (result.success) {
                this.showSuccess('测试邮件发送成功');
            } else {
                this.showError('测试邮件发送失败: ' + result.error);
            }
        } catch (error) {
            console.error('测试通知失败:', error);
            this.showError('测试邮件发送失败，请检查邮件配置');
        }
    }

    /**
     * 显示加载状态
     * @param {boolean} show - 是否显示
     */
    showLoading(show) {
        const loadingElement = document.getElementById('settings-loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * 显示错误信息
     * @param {string} message - 错误信息
     */
    showError(message) {
        console.error('系统设置错误:', message);
        // 这里可以集成到全局通知系统
        alert('错误: ' + message);
    }

    /**
     * 显示成功信息
     * @param {string} message - 成功信息
     */
    showSuccess(message) {
        console.log('系统设置成功:', message);
        // 这里可以集成到全局通知系统
        alert('成功: ' + message);
    }

    /**
     * 获取系统设置HTML模板
     * @returns {string} HTML模板
     */
    static getTemplate() {
        return `
            <div class="settings-container p-4 sm:p-6">
                <!-- 加载状态 -->
                <div id="settings-loading" class="text-center py-8" style="display: none;">
                    <div class="loading-dots">
                        <span style="--i: 0"></span>
                        <span style="--i: 1"></span>
                        <span style="--i: 2"></span>
                    </div>
                    <div class="mt-2 text-gray-600">加载中...</div>
                </div>
                
                <!-- 设置标签页 -->
                <div class="card mb-6">
                    <div class="card-body">
                        <div class="flex flex-wrap border-b border-gray-200">
                            <button data-tab="general" class="tab-button active text-sm sm:text-base">
                                <i data-lucide="settings" class="w-4 h-4 mr-2"></i>
                                通用设置
                            </button>
                            <button data-tab="scheduler" class="tab-button text-sm sm:text-base">
                                <i data-lucide="clock" class="w-4 h-4 mr-2"></i>
                                调度器
                            </button>
                            <button data-tab="notifications" class="tab-button text-sm sm:text-base">"tab-button">
                                <i data-lucide="bell" class="w-4 h-4 mr-2"></i>
                                通知
                            </button>
                            <button data-tab="security" class="tab-button text-sm sm:text-base">
                                <i data-lucide="shield" class="w-4 h-4 mr-2"></i>
                                安全
                            </button>
                            <button data-tab="advanced" class="tab-button text-sm sm:text-base">
                                <i data-lucide="code" class="w-4 h-4 mr-2"></i>
                                高级
                            </button>
                        </div>
                    </div>
                </div>
                
                <!-- 设置内容 -->
                <div class="card">
                    <div class="card-body">
                        <div data-tab-content="general" id="general-settings"></div>
                        <div data-tab-content="scheduler" id="scheduler-settings" style="display: none;"></div>
                        <div data-tab-content="notifications" id="notification-settings" style="display: none;"></div>
                        <div data-tab-content="security" id="security-settings" style="display: none;"></div>
                        <div data-tab-content="advanced" id="advanced-settings" style="display: none;"></div>
                    </div>
                    
                    <div class="card-footer">
                        <div class="flex justify-end space-x-3">
                            <button id="reset-settings" class="btn btn-outline">
                                <i data-lucide="rotate-ccw" class="w-4 h-4 mr-2"></i>
                                重置
                            </button>
                            <button id="save-settings" class="btn btn-outline" disabled>
                                <i data-lucide="save" class="w-4 h-4 mr-2"></i>
                                保存设置
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
}

// 创建全局实例
const settingsManager = new SettingsManager();

// 导出到全局
window.settingsManager = settingsManager;

// 如果支持模块化，也导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = settingsManager;
}

if (typeof define === 'function' && define.amd) {
    define([], function() {
        return settingsManager;
    });
}