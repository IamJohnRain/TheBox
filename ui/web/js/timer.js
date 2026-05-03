/**
 * @fileoverview 倒计时模块。
 *
 * 管理审讯倒计时的显示，包括时间格式化、
 * 30秒以下变红闪烁效果。
 *
 * @author The Box Dev Team
 */

/**
 * TimerManager - 倒计时管理类。
 *
 * 负责：
 * - 更新倒计时显示（格式 MM:SS）
 * - 30 秒以下切换为危险红色闪烁
 * - 60 秒以下切换为警告黄色
 * - 清空倒计时显示
 */
class TimerManager {
    /**
     * 创建 TimerManager 实例。
     */
    constructor() {
        /** @type {HTMLElement} 倒计时显示元素 */
        this.display = document.getElementById('timer-display');

        /** @type {number|null} 危险闪烁动画定时器 */
        this._dangerInterval = null;
    }

    /**
     * 更新倒计时显示。
     *
     * @param {number} timeLeft - 剩余秒数
     * @returns {void}
     *
     * @example
     * timerManager.update(300);  // 显示 "05:00"
     * timerManager.update(45);   // 显示 "00:45"，黄色警告
     * timerManager.update(15);   // 显示 "00:15"，红色闪烁
     */
    update(timeLeft) {
        if (!this.display) {
            console.error('[TimerManager] Display element not found');
            return;
        }

        if (timeLeft === null || timeLeft === undefined || isNaN(timeLeft)) {
            this.clear();
            return;
        }

        // 格式化为 MM:SS
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        this.display.textContent =
            `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

        // 更新样式类
        this.display.className = 'timer-display';

        if (timeLeft <= 30) {
            this.display.classList.add('danger');
        } else if (timeLeft <= 60) {
            this.display.classList.add('warning');
        }
    }

    /**
     * 清空倒计时显示，恢复初始状态。
     */
    clear() {
        if (this.display) {
            this.display.textContent = '--';
            this.display.className = 'timer-display';
        }
    }
}
