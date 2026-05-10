/**
 * @fileoverview Menu Manager - Story mode UI controller.
 */

class MenuManager {
    constructor() {
        this.menuEl = document.getElementById('main-menu');
        this.modeSelectorEl = document.getElementById('mode-selector');
        this.storyListEl = document.getElementById('story-list');
        this.storyCardsEl = document.getElementById('story-cards');
        this.narrativeOverlay = document.getElementById('narrative-overlay');
        this.endingOverlay = document.getElementById('ending-overlay');
        this.storyProgress = document.getElementById('story-progress');

        this._setupEventListeners();
    }

    _setupEventListeners() {
        const btnStoryMode = document.getElementById('btn-story-mode');
        const btnCustomMode = document.getElementById('btn-custom-mode');
        const btnBackToMenu = document.getElementById('btn-back-to-menu');
        const btnStartChapter = document.getElementById('btn-start-chapter');
        const btnReturnMainMenu = document.getElementById('btn-return-main-menu');

        btnStoryMode?.addEventListener('click', () => {
            this.showStoryList();
        });

        btnCustomMode?.addEventListener('click', () => {
            this.hide();
            if (window.bridge) {
                window.bridge.startCustomMode();
            }
        });

        btnBackToMenu?.addEventListener('click', () => {
            this.hideStoryList();
        });

        btnStartChapter?.addEventListener('click', () => {
            this.hideNarrative();
            if (window.bridge) {
                window.bridge.startChapter();
            }
        });

        btnReturnMainMenu?.addEventListener('click', () => {
            this.hideEnding();
            this.show();
        });
    }

    /**
     * Show the main menu.
     */
    show() {
        if (this.menuEl) {
            this.menuEl.classList.remove('hidden');
            this.menuEl.style.display = 'flex';
        }
    }

    /**
     * Hide the main menu.
     */
    hide() {
        if (this.menuEl) {
            this.menuEl.classList.add('hidden');
            this.menuEl.style.display = 'none';
        }
    }

    /**
     * Show the story list panel.
     */
    showStoryList() {
        if (this.modeSelectorEl) {
            this.modeSelectorEl.style.display = 'none';
        }
        if (this.storyListEl) {
            this.storyListEl.style.display = 'block';
        }
        if (window.bridge) {
            window.bridge.requestStoryList();
        }
    }

    /**
     * Hide the story list panel and show mode selector.
     */
    hideStoryList() {
        if (this.modeSelectorEl) {
            this.modeSelectorEl.style.display = 'flex';
        }
        if (this.storyListEl) {
            this.storyListEl.style.display = 'none';
        }
    }

    /**
     * Load stories into the story list.
     * @param {Array} stories - Array of story objects with {story_id, title, desc, chapter_count}
     */
    loadStoryList(stories) {
        if (!this.storyCardsEl) return;

        this.storyCardsEl.innerHTML = '';

        if (!stories || stories.length === 0) {
            this.storyCardsEl.innerHTML = '<p class="text-muted">暂无可用剧情</p>';
            return;
        }

        stories.forEach(story => {
            const card = document.createElement('div');
            card.className = 'story-card';
            card.innerHTML = `
                <div class="story-card-info">
                    <div class="story-card-title">${this._escapeHtml(story.title)}</div>
                    <div class="story-card-desc">${this._escapeHtml(story.desc || '')}</div>
                    <div class="story-card-meta">${story.chapter_count || 0} 章节</div>
                </div>
                <span class="story-card-arrow">→</span>
            `;
            card.addEventListener('click', () => {
                if (window.bridge) {
                    window.bridge.startStoryMode(story.story_id);
                }
            });
            this.storyCardsEl.appendChild(card);
        });
    }

    /**
     * Show narrative overlay.
     * @param {string} chapterNumber - Chapter number label (e.g., "第一章")
     * @param {string} chapterTitle - Chapter title
     * @param {string} narrativeText - Narrative text content
     */
    showNarrative(chapterNumber, chapterTitle, narrativeText) {
        const chapterNumberEl = document.getElementById('chapter-number');
        const chapterTitleEl = document.getElementById('chapter-title');
        const narrativeTextEl = document.getElementById('narrative-text');

        if (chapterNumberEl) chapterNumberEl.textContent = chapterNumber;
        if (chapterTitleEl) chapterTitleEl.textContent = chapterTitle;
        if (narrativeTextEl) narrativeTextEl.textContent = narrativeText;

        if (this.narrativeOverlay) {
            this.narrativeOverlay.classList.remove('hidden');
            this.narrativeOverlay.style.display = 'flex';
        }
    }

    /**
     * Hide narrative overlay.
     */
    hideNarrative() {
        if (this.narrativeOverlay) {
            this.narrativeOverlay.classList.add('hidden');
            this.narrativeOverlay.style.display = 'none';
        }
    }

    /**
     * Show ending overlay.
     * @param {string} title - Ending title
     * @param {string} desc - Ending description
     * @param {string} narrative - Ending narrative text
     */
    showEnding(title, desc, narrative) {
        const endingTitleEl = document.getElementById('ending-title');
        const endingDescEl = document.getElementById('ending-desc');
        const endingNarrativeEl = document.getElementById('ending-narrative');

        if (endingTitleEl) endingTitleEl.textContent = title;
        if (endingDescEl) endingDescEl.textContent = desc;
        if (endingNarrativeEl) endingNarrativeEl.textContent = narrative;

        if (this.endingOverlay) {
            this.endingOverlay.classList.remove('hidden');
            this.endingOverlay.style.display = 'flex';
        }
    }

    /**
     * Hide ending overlay.
     */
    hideEnding() {
        if (this.endingOverlay) {
            this.endingOverlay.classList.add('hidden');
            this.endingOverlay.style.display = 'none';
        }
    }

    /**
     * Update story progress bar.
     * @param {number} current - Current chapter number
     * @param {number} total - Total number of chapters
     */
    updateProgress(current, total) {
        const chapterIndicatorEl = document.getElementById('chapter-indicator');
        const progressFillEl = document.getElementById('story-progress-fill');

        if (chapterIndicatorEl) {
            chapterIndicatorEl.textContent = `第${current}章 / 共${total}章`;
        }
        if (progressFillEl && total > 0) {
            progressFillEl.style.width = `${(current / total) * 100}%`;
        }
    }

    /**
     * Show story progress bar.
     */
    showProgress() {
        if (this.storyProgress) {
            this.storyProgress.classList.remove('hidden');
            this.storyProgress.style.display = 'flex';
        }
    }

    /**
     * Hide story progress bar.
     */
    hideProgress() {
        if (this.storyProgress) {
            this.storyProgress.classList.add('hidden');
            this.storyProgress.style.display = 'none';
        }
    }

    /**
     * Escape HTML to prevent XSS.
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    _escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize menu manager when DOM is ready
let menuManager;

function initMenuManager() {
    if (!menuManager) {
        menuManager = new MenuManager();
        window.menuManager = menuManager;
    }
    return menuManager;
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMenuManager);
} else {
    initMenuManager();
}