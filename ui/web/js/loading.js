/**
 * @fileoverview 加载状态模块。
 *
 * 管理加载遮罩层的显示和隐藏，包括进度更新
 * 和取消按钮的交互逻辑。
 *
 * @author The Box Dev Team
 */

/**
 * LoadingManager - 加载状态管理类。
 *
 * 负责：
 * - 显示带消息和可取消选项的加载遮罩层
 * - 隐藏加载遮罩层
 * - 更新等待时间进度
 * - 取消按钮调用 bridge.cancelOperation()
 */
class LoadingManager {
    /**
     * 创建 LoadingManager 实例。
     */
    constructor() {
        /** @type {HTMLElement} 加载遮罩层 */
        this.overlay = document.getElementById('loading-overlay');

        /** @type {HTMLElement} 加载文本 */
        this.textEl = document.getElementById('loading-text');

        /** @type {HTMLElement} 加载状态（等待时间） */
        this.statusEl = document.getElementById('loading-status');

        /** @type {HTMLButtonElement} 取消按钮 */
        this.cancelBtn = document.getElementById('loading-cancel');

        /** @type {number|null} 进度更新定时器 */
        this._updateInterval = null;

        /** @type {boolean} 是否可取消 */
        this._cancellable = false;

        this._bindEvents();
    }

    /**
     * 绑定取消按钮事件。
     * @private
     */
    _bindEvents() {
        if (this.cancelBtn) {
            this.cancelBtn.addEventListener('click', () => {
                if (window.bridge) {
                    window.bridge.cancelOperation();
                }
                this.hide();
            });
        }
    }

    /**
     * 显示加载遮罩层。
     *
     * @param {string} [message='正在处理...'] - 加载提示消息
     * @param {boolean} [cancellable=false] - 是否显示取消按钮
     * @returns {void}
     *
     * @example
     * loadingManager.show('正在生成案件...', true);
     * loadingManager.show('正在处理...');
     */
    show(message, cancellable) {
        if (!this.overlay) {
            console.error('[LoadingManager] Overlay element not found');
            return;
        }

        // 设置文本
        if (this.textEl) {
            this.textEl.textContent = message || '正在处理...';
        }

        // 设置状态
        if (this.statusEl) {
            this.statusEl.textContent = '已等待 0s';
        }

        // 控制取消按钮显示
        this._cancellable = Boolean(cancellable);
        if (this.cancelBtn) {
            this.cancelBtn.style.display = this._cancellable ? 'inline-block' : 'none';
        }

        // 显示遮罩
        this.overlay.classList.add('active');

        // 启动进度更新
        this._startProgressUpdate();
    }

    /**
     * 隐藏加载遮罩层。
     */
    hide() {
        if (this.overlay) {
            this.overlay.classList.remove('active');
        }

        // 停止进度更新
        this._stopProgressUpdate();
    }

    /**
     * 更新加载进度（由后端 update_loading_progress 信号驱动）。
     *
     * @param {number} elapsedSeconds - 已等待秒数
     * @returns {void}
     */
    updateProgress(elapsedSeconds) {
        if (this.statusEl && typeof elapsedSeconds === 'number') {
            this.statusEl.textContent = `已等待 ${elapsedSeconds}s`;
        }
    }

    /**
     * 启动进度计时器。
     * @private
     */
    _startProgressUpdate() {
        this._stopProgressUpdate();

        let elapsed = 0;
        this._updateInterval = setInterval(() => {
            elapsed++;
            if (this.statusEl) {
                this.statusEl.textContent = `已等待 ${elapsed}s`;
            }
        }, 1000);
    }

    /**
     * 停止进度计时器。
     * @private
     */
    _stopProgressUpdate() {
        if (this._updateInterval) {
            clearInterval(this._updateInterval);
            this._updateInterval = null;
        }
    }
}
