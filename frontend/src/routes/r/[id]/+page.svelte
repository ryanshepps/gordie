<script lang="ts">
	import { page } from '$app/state';

	const API_URL = import.meta.env.VITE_API_URL || 'https://gordie.lastingsoftware.ca';

	interface Message {
		role: 'human' | 'ai';
		content: string;
	}

	let messages = $state<Message[]>([]);
	let inputText = $state('');
	let isStreaming = $state(false);
	let isLoadingHistory = $state(true);
	let error = $state('');
	let messagesContainer: HTMLElement | undefined = $state();
	let textareaEl: HTMLTextAreaElement | undefined = $state();

	const webThreadId = $derived(page.params.id);
	const canSend = $derived(inputText.trim().length > 0 && !isStreaming);

	function scrollToBottom() {
		if (messagesContainer) {
			messagesContainer.scrollTop = messagesContainer.scrollHeight;
		}
	}

	async function loadHistory() {
		try {
			const res = await fetch(`${API_URL}/api/chat/${webThreadId}/history`);
			if (res.status === 404) {
				error = 'Conversation not found.';
				isLoadingHistory = false;
				return;
			}
			if (!res.ok) {
				error = 'Failed to load conversation history.';
				isLoadingHistory = false;
				return;
			}
			const data = await res.json();
			messages = data.messages ?? [];
		} catch {
			error = 'Failed to connect to server.';
		}
		isLoadingHistory = false;
	}

	async function sendMessage() {
		const text = inputText.trim();
		if (!text || isStreaming) return;

		error = '';
		inputText = '';
		messages = [...messages, { role: 'human', content: text }];
		// Add placeholder for streaming AI response
		messages = [...messages, { role: 'ai', content: '' }];
		isStreaming = true;

		// Reset textarea height
		if (textareaEl) {
			textareaEl.style.height = 'auto';
		}

		try {
			const res = await fetch(`${API_URL}/api/chat`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ web_thread_id: webThreadId, message: text })
			});

			if (res.status === 429) {
				error = 'Too many messages. Please wait a moment.';
				// Remove placeholder
				messages = messages.slice(0, -1);
				isStreaming = false;
				return;
			}

			if (res.status === 404) {
				error = 'Conversation not found.';
				messages = messages.slice(0, -1);
				isStreaming = false;
				return;
			}

			if (!res.ok || !res.body) {
				error = 'Failed to send message.';
				messages = messages.slice(0, -1);
				isStreaming = false;
				return;
			}

			const reader = res.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';
			let currentEvent = '';

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() ?? '';

				for (const line of lines) {
					if (line.startsWith('event: ')) {
						currentEvent = line.slice(7).trim();
					} else if (line.startsWith('data: ')) {
						const dataStr = line.slice(6);
						try {
							const payload = JSON.parse(dataStr);

							if (currentEvent === 'token' && payload.token) {
								const lastIdx = messages.length - 1;
								const lastMsg = messages[lastIdx];
								messages = [
									...messages.slice(0, lastIdx),
									{ ...lastMsg, content: lastMsg.content + payload.token }
								];
							} else if (currentEvent === 'error') {
								error = payload.error || 'An error occurred.';
							}
						} catch {
							// Skip malformed JSON
						}
						currentEvent = '';
					}
				}
			}
		} catch {
			error = 'Failed to connect to server.';
			// Remove empty placeholder if no content was streamed
			const lastMsg = messages[messages.length - 1];
			if (lastMsg?.role === 'ai' && !lastMsg.content) {
				messages = messages.slice(0, -1);
			}
		}

		isStreaming = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
		}
	}

	function autoResize(e: Event) {
		const target = e.target as HTMLTextAreaElement;
		target.style.height = 'auto';
		target.style.height = Math.min(target.scrollHeight, 120) + 'px';
	}

	$effect(() => {
		loadHistory();
	});

	$effect(() => {
		// Scroll to bottom when messages change
		if (messages.length > 0) {
			// Use tick to wait for DOM update
			requestAnimationFrame(scrollToBottom);
		}
	});
</script>

<svelte:head>
	<title>Chat with Gordie</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="chat-app">
	<header class="chat-header">
		<a href="/" class="chat-logo">
			<img src="/logo.svg" alt="" class="chat-logo-img" />
			<span class="chat-logo-text">Gordie</span>
		</a>
	</header>

	{#if error}
		<div class="error-banner" role="alert">
			<span>{error}</span>
			<button class="error-dismiss" onclick={() => (error = '')}>Dismiss</button>
		</div>
	{/if}

	<div class="messages-area" bind:this={messagesContainer}>
		{#if isLoadingHistory}
			<div class="loading-state">
				<div class="typing-indicator">
					<span></span><span></span><span></span>
				</div>
				<p class="loading-text">Loading conversation...</p>
			</div>
		{:else if messages.length === 0 && !error}
			<div class="empty-state">
				<p class="empty-title">Ask Gordie anything</p>
				<p class="empty-subtitle">Fantasy hockey advice, lineup help, trade analysis</p>
			</div>
		{:else}
			<div class="messages-list">
				{#each messages as msg, i}
					<div class="message-row" class:message-human={msg.role === 'human'} class:message-ai={msg.role === 'ai'}>
						<div class="message-bubble" class:bubble-human={msg.role === 'human'} class:bubble-ai={msg.role === 'ai'}>
							{#if msg.content}
								{msg.content}
							{:else if msg.role === 'ai' && isStreaming && i === messages.length - 1}
								<div class="typing-indicator">
									<span></span><span></span><span></span>
								</div>
							{/if}
							{#if msg.role === 'ai' && isStreaming && i === messages.length - 1 && msg.content}
								<span class="cursor-blink">|</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<div class="input-area">
		<form class="input-form" onsubmit={(e) => { e.preventDefault(); sendMessage(); }}>
			<textarea
				bind:this={textareaEl}
				bind:value={inputText}
				onkeydown={handleKeydown}
				oninput={autoResize}
				placeholder="Message Gordie..."
				rows="1"
				disabled={isStreaming || isLoadingHistory}
				class="chat-input"
			></textarea>
			<button
				type="submit"
				disabled={!canSend}
				class="send-btn"
				aria-label="Send message"
			>
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<line x1="22" y1="2" x2="11" y2="13"></line>
					<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
				</svg>
			</button>
		</form>
	</div>
</div>

<style>
	.chat-app {
		display: flex;
		flex-direction: column;
		height: 100dvh;
		background: var(--color-bg);
		color: var(--color-text);
	}

	/* Header */
	.chat-header {
		display: flex;
		align-items: center;
		height: 56px;
		padding: 0 1rem;
		background: rgba(15, 13, 9, 0.9);
		backdrop-filter: blur(12px);
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}

	.chat-logo {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--color-text);
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.chat-logo:hover {
		text-decoration: none;
		color: var(--color-accent);
	}

	.chat-logo-img {
		height: 28px;
		width: 28px;
	}

	/* Error */
	.error-banner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.625rem 1rem;
		background: rgba(255, 71, 87, 0.15);
		color: var(--color-error);
		font-size: 0.875rem;
		flex-shrink: 0;
	}

	.error-dismiss {
		background: none;
		border: none;
		color: var(--color-error);
		cursor: pointer;
		font-size: 0.8rem;
		text-decoration: underline;
	}

	/* Messages area */
	.messages-area {
		flex: 1;
		overflow-y: auto;
		padding: 1rem;
		scroll-behavior: smooth;
	}

	.messages-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		max-width: 720px;
		margin: 0 auto;
	}

	/* Loading / Empty */
	.loading-state,
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		height: 100%;
		gap: 0.75rem;
		color: var(--color-text-muted);
	}

	.loading-text {
		font-size: 0.875rem;
	}

	.empty-title {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text);
	}

	.empty-subtitle {
		font-size: 0.9rem;
	}

	/* Message rows */
	.message-row {
		display: flex;
	}

	.message-human {
		justify-content: flex-end;
	}

	.message-ai {
		justify-content: flex-start;
	}

	/* Bubbles */
	.message-bubble {
		max-width: 80%;
		padding: 0.625rem 0.875rem;
		border-radius: 0.75rem;
		font-size: 0.9375rem;
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.bubble-human {
		background: var(--color-primary);
		color: #0F0D09;
		border-bottom-right-radius: 0.25rem;
	}

	.bubble-ai {
		background: var(--color-bg-card);
		border: 1px solid var(--color-border);
		color: var(--color-text);
		border-bottom-left-radius: 0.25rem;
	}

	/* Typing indicator */
	.typing-indicator {
		display: inline-flex;
		gap: 4px;
		align-items: center;
		padding: 2px 0;
	}

	.typing-indicator span {
		display: block;
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--color-text-muted);
		animation: typing-pulse 1.4s ease-in-out infinite;
	}

	.typing-indicator span:nth-child(2) {
		animation-delay: 0.2s;
	}

	.typing-indicator span:nth-child(3) {
		animation-delay: 0.4s;
	}

	@keyframes typing-pulse {
		0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
		30% { opacity: 1; transform: scale(1); }
	}

	/* Cursor blink */
	.cursor-blink {
		animation: blink 0.8s step-end infinite;
		color: var(--color-primary);
		font-weight: 300;
	}

	@keyframes blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0; }
	}

	/* Input area */
	.input-area {
		flex-shrink: 0;
		padding: 0.75rem 1rem;
		padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
		background: var(--color-bg-secondary);
		border-top: 1px solid var(--color-border);
	}

	.input-form {
		display: flex;
		align-items: flex-end;
		gap: 0.5rem;
		max-width: 720px;
		margin: 0 auto;
	}

	.chat-input {
		flex: 1;
		resize: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		background: var(--color-bg);
		color: var(--color-text);
		font-family: var(--font-sans);
		font-size: 0.9375rem;
		padding: 0.625rem 0.75rem;
		line-height: 1.4;
		outline: none;
		transition: border-color 0.15s ease-out;
	}

	.chat-input:focus {
		border-color: var(--color-primary);
	}

	.chat-input::placeholder {
		color: var(--color-text-muted);
	}

	.chat-input:disabled {
		opacity: 0.5;
	}

	.send-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 40px;
		height: 40px;
		border-radius: 0.375rem;
		border: none;
		background: var(--color-primary);
		color: #0F0D09;
		cursor: pointer;
		flex-shrink: 0;
		transition: background 0.15s ease-out, transform 0.1s ease-out;
	}

	.send-btn:hover:not(:disabled) {
		background: var(--color-primary-hover);
	}

	.send-btn:active:not(:disabled) {
		transform: scale(0.95);
	}

	.send-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	/* Reduced motion */
	@media (prefers-reduced-motion: reduce) {
		.typing-indicator span {
			animation: none;
			opacity: 0.6;
		}
		.cursor-blink {
			animation: none;
		}
		.messages-area {
			scroll-behavior: auto;
		}
	}
</style>
