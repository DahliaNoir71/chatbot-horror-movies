import { type Ref, watch, onUnmounted } from 'vue'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

export function useFocusTrap(containerRef: Ref<HTMLElement | null>) {
  let active = false

  function getFocusableElements(): HTMLElement[] {
    if (!containerRef.value) return []
    return Array.from(
      containerRef.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
    )
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key !== 'Tab' || !active) return

    const focusable = getFocusableElements()
    if (focusable.length === 0) return

    const first: HTMLElement | undefined = focusable[0]
    const last: HTMLElement | undefined = focusable[focusable.length - 1]
    if (!first || !last) return

    if (event.shiftKey) {
      if (document.activeElement === first) {
        event.preventDefault()
        last.focus()
      }
    } else {
      if (document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
  }

  function activate() {
    active = true
    document.addEventListener('keydown', handleKeyDown)
  }

  function deactivate() {
    active = false
    document.removeEventListener('keydown', handleKeyDown)
  }

  watch(containerRef, (el) => {
    if (el) {
      activate()
    } else {
      deactivate()
    }
  })

  onUnmounted(() => {
    deactivate()
  })

  return { activate, deactivate }
}
