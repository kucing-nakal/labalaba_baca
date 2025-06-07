document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    let novelFolder = '';
    let chapters = [];
    let currentChapterIndex = 0;

    // --- DOM ELEMENT CACHING ---
    const novelTitleEl = document.getElementById('novel-title');
    const chapterContentEl = document.getElementById('chapter-content');
    const chapterIndicatorEl = document.getElementById('chapter-indicator');
    const prevBtn = document.getElementById('prev-chapter-btn');
    const nextBtn = document.getElementById('next-chapter-btn');
    
    // --- MODAL & SETTINGS ELEMENTS ---
    const chapterModal = document.getElementById('chapter-modal');
    const settingsModal = document.getElementById('settings-modal');
    const chapterListEl = document.getElementById('chapter-list');
    const chapterSearchEl = document.getElementById('chapter-search');
    const fontSizeSlider = document.getElementById('font-size');
    const fontSizeValueEl = document.getElementById('font-size-value');
    const lineHeightSlider = document.getElementById('line-height');
    const lineHeightValueEl = document.getElementById('line-height-value');

    // --- CORE FUNCTIONS ---

    const loadChapter = async (index) => {
        if (index < 0 || index >= chapters.length) return;
        
        currentChapterIndex = index;
        const chapter = chapters[index];
        chapterContentEl.innerHTML = `<p class="loading-text">Loading Chapter ${chapter.number}: ${chapter.title}...</p>`;

        const llmPath = `${novelFolder}/llm_chapters/${chapter.file}`;
        const rawPath = `${novelFolder}/raw_chapters/${chapter.file}`;

        try {
            let response = await fetch(llmPath);
            if (response.status === 404) { // Check specifically for 404
                console.log(`LLM version not found, trying raw version.`);
                response = await fetch(rawPath);
            }
            if (!response.ok) throw new Error(`Chapter file not found at ${response.url}`);
            
            const text = await response.text();
            chapterContentEl.textContent = text; // Use textContent for security and to preserve whitespace
            window.scrollTo(0, 0);
            updateUI();
            localStorage.setItem(`lastChapter-${novelFolder}`, index);
        } catch (error) {
            chapterContentEl.innerHTML = `<p class="loading-text">Failed to load chapter. Please try again.</p>`;
            console.error(error);
        }
    };

    const updateUI = () => {
        prevBtn.disabled = currentChapterIndex === 0;
        nextBtn.disabled = currentChapterIndex === chapters.length - 1;
        chapterIndicatorEl.textContent = `Chapter ${currentChapterIndex + 1} / ${chapters.length}`;
    };

    const populateChapterList = (chaptersToRender) => {
        chapterListEl.innerHTML = chaptersToRender.map((chap, i) => 
            `<a href="#" data-index="${chapters.indexOf(chap)}">${chap.number}. ${chap.title}</a>`
        ).join('');
    };

    const applySetting = (key, value) => {
        localStorage.setItem(key, value);
        switch (key) {
            case 'fontSize':
                chapterContentEl.style.fontSize = `${value}px`;
                fontSizeValueEl.textContent = `${value}px`;
                break;
            case 'lineHeight':
                chapterContentEl.style.lineHeight = value;
                lineHeightValueEl.textContent = value;
                break;
            case 'theme':
                document.documentElement.setAttribute('data-theme', value);
                break;
        }
    };

    const loadSettings = () => {
        const settings = {
            fontSize: localStorage.getItem('fontSize') || '18',
            lineHeight: localStorage.getItem('lineHeight') || '1.8',
            theme: localStorage.getItem('theme') || 'light'
        };
        fontSizeSlider.value = settings.fontSize;
        lineHeightSlider.value = settings.lineHeight;
        Object.keys(settings).forEach(key => applySetting(key, settings[key]));
    };
    
    // --- INITIALIZATION ---

    const init = async () => {
        const params = new URLSearchParams(window.location.search);
        novelFolder = params.get('novel');
        if (!novelFolder) {
            novelTitleEl.textContent = 'Novel not found in URL.';
            return;
        }

        const readableTitle = novelFolder.replace(/-/g, ' ');
        novelTitleEl.textContent = readableTitle;
        document.title = readableTitle;

        try {
            const response = await fetch(`${novelFolder}/manifest.json`);
            if (!response.ok) throw new Error('Novel manifest not found.');
            chapters = await response.json();
            populateChapterList(chapters);

            const lastChapterIndex = parseInt(localStorage.getItem(`lastChapter-${novelFolder}`), 10) || 0;
            loadChapter(lastChapterIndex);

        } catch (error) {
            novelTitleEl.textContent = 'Could not load novel.';
            console.error(error);
        }
    };

    // --- EVENT LISTENERS ---

    // Navigation
    prevBtn.addEventListener('click', () => loadChapter(currentChapterIndex - 1));
    nextBtn.addEventListener('click', () => loadChapter(currentChapterIndex + 1));
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') prevBtn.click();
        if (e.key === 'ArrowRight') nextBtn.click();
    });

    // Modals
    const chapterListBtn = document.getElementById('chapter-list-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const modals = document.querySelectorAll('.modal');

    chapterListBtn.addEventListener('click', () => {
        console.log("Chapter list button clicked");
        chapterModal.classList.add('visible');
    });

    settingsBtn.addEventListener('click', () => {
        console.log("Settings button clicked");
        settingsModal.classList.add('visible');
    });

    // Add a single listener for all close buttons
    modals.forEach(modal => {
        modal.querySelector('.close-btn').addEventListener('click', () => {
            modal.classList.remove('visible');
        });
    });

    // Chapter List
    chapterListEl.addEventListener('click', (e) => {
        if (e.target.tagName === 'A') {
            e.preventDefault();
            loadChapter(parseInt(e.target.dataset.index, 10));
            chapterModal.classList.remove('visible');
        }
    });
    chapterSearchEl.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filteredChapters = chapters.filter(c => c.title.toLowerCase().includes(searchTerm));
        populateChapterList(filteredChapters);
    });

    // Settings
    fontSizeSlider.addEventListener('input', (e) => applySetting('fontSize', e.target.value));
    lineHeightSlider.addEventListener('input', (e) => applySetting('lineHeight', e.target.value));
    document.getElementById('theme-toggle').addEventListener('click', () => {
        const newTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applySetting('theme', newTheme);
    });

    loadSettings();
    init();
});
