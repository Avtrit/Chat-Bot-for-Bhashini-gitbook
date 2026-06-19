document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const sidebar = document.getElementById("sidebar-container");
    const menuToggle = document.getElementById("menu-toggle");
    const closeSidebar = document.getElementById("close-sidebar");
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const chatMessages = document.getElementById("chat-messages");
    const welcomeContainer = document.getElementById("welcome-container");
    const loadingIndicator = document.getElementById("loading-indicator");
    const clearChatBtn = document.getElementById("clear-chat-btn");
    const openaiStatus = document.getElementById("openai-key-status");
    const groqStatus = document.getElementById("groq-key-status");
    
    // Sliders & Selects
    const providerSelect = document.getElementById("provider-select");
    const modelInput = document.getElementById("model-input");
    const tempSlider = document.getElementById("temp-slider");
    const tempVal = document.getElementById("temp-val");
    const kSlider = document.getElementById("k-slider");
    const kVal = document.getElementById("k-val");

    // Chat History State
    let chatHistory = []; // { role: "user" | "assistant", content: "..." }

    // 1. Check API Settings on Load
    async function checkSettings() {
        try {
            const res = await fetch("/api/settings");
            if (!res.ok) throw new Error("Failed to load settings");
            const data = await res.json();
            
            // Update Groq Key status indicator
            if (data.groq_available) {
                if (groqStatus) groqStatus.innerHTML = '<span class="text-green"><i class="fa-solid fa-circle-check"></i> Configured</span>';
            } else {
                if (groqStatus) groqStatus.innerHTML = '<span style="color: #f59e0b;"><i class="fa-solid fa-circle-exclamation"></i> Not Configured</span>';
            }

            // Update OpenAI Key status indicator
            if (data.openai_available) {
                openaiStatus.innerHTML = '<span class="text-green"><i class="fa-solid fa-circle-check"></i> Configured</span>';
            } else {
                openaiStatus.innerHTML = '<span style="color: #f59e0b;"><i class="fa-solid fa-circle-exclamation"></i> Not Configured</span>';
            }

            // Update provider value and input placeholder
            providerSelect.value = data.default_provider;
            updateModelPlaceholder(data.default_provider, data);
        } catch (err) {
            console.error("Error checking settings:", err);
            if (groqStatus) groqStatus.innerHTML = '<span style="color: #ef4444;"><i class="fa-solid fa-circle-xmark"></i> Connection Error</span>';
            openaiStatus.innerHTML = '<span style="color: #ef4444;"><i class="fa-solid fa-circle-xmark"></i> Connection Error</span>';
        }
    }
    checkSettings();

    function updateModelPlaceholder(provider, data) {
        if (provider === "groq") {
            modelInput.placeholder = `e.g. ${data?.default_groq_model || 'llama-3.3-70b-versatile'}`;
        } else if (provider === "openai") {
            modelInput.placeholder = `e.g. ${data?.default_openai_model || 'gpt-4o-mini'}`;
        } else if (provider === "ollama") {
            modelInput.placeholder = `e.g. ${data?.default_ollama_model || 'llama3'}`;
        } else {
            modelInput.placeholder = "Leave blank for default";
        }
    }

    // Update placeholder on dropdown change
    providerSelect.addEventListener("change", () => {
        updateModelPlaceholder(providerSelect.value);
    });

    // 2. Event Listeners for UI interaction
    menuToggle.addEventListener("click", () => sidebar.classList.add("open"));
    closeSidebar.addEventListener("click", () => sidebar.classList.remove("open"));

    // Close sidebar when clicking outside on mobile
    document.addEventListener("click", (e) => {
        if (window.innerWidth <= 768) {
            if (!sidebar.contains(e.target) && !menuToggle.contains(e.target)) {
                sidebar.classList.remove("open");
            }
        }
    });

    // Auto-resize textarea
    userInput.addEventListener("input", function() {
        this.style.height = "auto";
        this.style.height = (this.scrollHeight - 4) + "px";
    });

    // Update Slider Value displays
    tempSlider.addEventListener("input", (e) => tempVal.textContent = e.target.value);
    kSlider.addEventListener("input", (e) => kVal.textContent = e.target.value);

    // Suggestion Cards click handler
    document.querySelectorAll(".suggestion-card").forEach(card => {
        card.addEventListener("click", () => {
            const query = card.getAttribute("data-query");
            userInput.value = query;
            userInput.dispatchEvent(new Event("input")); // trigger auto-resize
            submitMessage(query);
        });
    });

    // Clear Chat
    clearChatBtn.addEventListener("click", () => {
        if (confirm("Are you sure you want to clear chat history?")) {
            chatMessages.innerHTML = "";
            chatHistory = [];
            welcomeContainer.style.display = "flex";
        }
    });

    // Submit handler
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (!text) return;
        submitMessage(text);
    });

    // Support Shift+Enter for newline, Enter for submit
    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event("submit"));
        }
    });

    // 3. Core Logic for message submission and response rendering
    async function submitMessage(messageText) {
        // Clear input field and reset height
        userInput.value = "";
        userInput.style.height = "auto";
        
        // Hide welcome screen
        welcomeContainer.style.display = "none";

        // Append user message to view and history state
        appendMessage("user", messageText);
        chatHistory.push({ role: "user", content: messageText });

        // Show loading bubble
        showLoader(true);

        try {
            // Retrieve current configurations
            const payload = {
                message: messageText,
                history: chatHistory.slice(-10), // Limit history context
                provider: providerSelect.value,
                model: modelInput.value.trim() || null,
                k: parseInt(kSlider.value),
                temperature: parseFloat(tempSlider.value)
            };

            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Server error occurred");
            }

            const data = await response.json();
            
            // Append assistant response
            appendMessage("assistant", data.answer, data.sources);
            chatHistory.push({ role: "assistant", content: data.answer });

        } catch (err) {
            console.error("Chat Error:", err);
            appendError(err.message || "Failed to contact the chatbot server.");
        } finally {
            showLoader(false);
        }
    }

    // Loader visibility toggler
    function showLoader(show) {
        if (show) {
            loadingIndicator.classList.add("active");
            scrollToBottom();
        } else {
            loadingIndicator.classList.remove("active");
        }
    }

    // Scroll chat view to bottom
    function scrollToBottom() {
        const wrapper = document.getElementById("messages-wrapper");
        wrapper.scrollTop = wrapper.scrollHeight;
    }

    // Append standard User or Assistant message
    function appendMessage(role, text, sources = []) {
        const bubble = document.createElement("div");
        bubble.className = `message-bubble ${role}-message`;
        
        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const avatarIcon = role === "user" ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';
        const senderName = role === "user" ? "You" : "Bhashini Assistant";
        
        let contentHtml = `
            <div class="avatar">${avatarIcon}</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="sender-name">${senderName}</span>
                    <span class="timestamp">${timestamp}</span>
                </div>
                <div class="message-text">
                    ${parseMarkdown(text)}
        `;

        // Render sources accordion drawer if there are sources
        if (role === "assistant" && sources && sources.length > 0) {
            const accordionId = `accordion-${Date.now()}`;
            contentHtml += `
                <div class="sources-card" id="${accordionId}">
                    <div class="sources-header" onclick="document.getElementById('${accordionId}').classList.toggle('open')">
                        <span class="sources-title">
                            <i class="fa-solid fa-receipt"></i> Retrieved Sources (${sources.length} chunks used)
                        </span>
                        <i class="fa-solid fa-chevron-down sources-icon"></i>
                    </div>
                    <div class="sources-content">
            `;
            
            sources.forEach(src => {
                contentHtml += `
                    <div class="source-item">
                        <div class="source-meta">
                            <span class="source-topic"><i class="fa-solid fa-folder-open"></i> ${escapeHtml(src.topic)}</span>
                            <span class="source-pages"><i class="fa-solid fa-file-lines"></i> ${escapeHtml(src.source)}</span>
                        </div>
                        <div class="source-snippet">${escapeHtml(src.content)}</div>
                    </div>
                `;
            });

            contentHtml += `
                    </div>
                </div>
            `;
        }

        contentHtml += `
                </div>
            </div>
        `;
        
        bubble.innerHTML = contentHtml;
        chatMessages.appendChild(bubble);
        scrollToBottom();
    }

    // Append Error alert
    function appendError(errorText) {
        const bubble = document.createElement("div");
        bubble.className = "message-bubble bot-message";
        
        bubble.innerHTML = `
            <div class="avatar" style="background: var(--bg-card); color: #ef4444;"><i class="fa-solid fa-circle-exclamation"></i></div>
            <div class="message-content">
                <div class="message-text" style="border-color: rgba(239, 68, 68, 0.2); background: rgba(239, 68, 68, 0.04);">
                    <p style="color: #ef4444; font-weight: 500; margin-bottom: 4px;"><i class="fa-solid fa-triangle-exclamation"></i> Action Failed</p>
                    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 0;">${escapeHtml(errorText)}</p>
                </div>
            </div>
        `;
        
        chatMessages.appendChild(bubble);
        scrollToBottom();
    }

    // 4. Utility Markdown / HTML Parsers
    function escapeHtml(str) {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function parseMarkdown(markdownText) {
        if (!markdownText) return "";
        
        let html = escapeHtml(markdownText);

        // Code Blocks ```language ... ```
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const languageLabel = lang ? `<span style="font-size: 10px; color: var(--text-details); display: block; margin-bottom: 6px; text-transform: uppercase;">${lang}</span>` : "";
            return `<pre>${languageLabel}<code>${code.trim()}</code></pre>`;
        });

        // Inline Code `code`
        html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

        // Bold Text **text**
        html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

        // Lists (Bullets)
        html = html.replace(/^[\s]*[-*][\s]+(.*)$/gm, "<li>$1</li>");
        html = html.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");

        // Format regular lines / paragraphs (ignoring existing block elements)
        const lines = html.split("\n");
        let parsedLines = [];
        let inList = false;

        for (let line of lines) {
            let trimmed = line.trim();
            if (trimmed.startsWith("<li>")) {
                if (!inList) {
                    parsedLines.push("<ul>");
                    inList = true;
                }
                parsedLines.push(line);
            } else {
                if (inList) {
                    parsedLines.push("</ul>");
                    inList = false;
                }
                if (trimmed && !trimmed.startsWith("<pre>") && !trimmed.endsWith("</pre>") && !trimmed.startsWith("<ul>") && !trimmed.startsWith("</ul>")) {
                    parsedLines.push(`<p>${line}</p>`);
                } else {
                    parsedLines.push(line);
                }
            }
        }
        if (inList) {
            parsedLines.push("</ul>");
        }

        return parsedLines.join("\n");
    }
});
