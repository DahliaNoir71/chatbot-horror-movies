import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseModal from '../BaseModal.vue'

// Mock useScrollLock since jsdom doesn't support it
vi.mock('@vueuse/core', () => ({
  useScrollLock: vi.fn(() => ({ value: false })),
}))

describe('BaseModal', () => {
  const defaultProps = { open: true, title: 'Test Modal' }

  it('does not render when open=false', () => {
    const wrapper = mount(BaseModal, {
      props: { open: false, title: 'Hidden' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('renders dialog with role="dialog" when open=true', () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  })

  it('has aria-modal="true"', () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[role="dialog"]').attributes('aria-modal')).toBe(
      'true'
    )
  })

  it('has aria-labelledby pointing to title element', () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      global: { stubs: { Teleport: true } },
    })
    const dialog = wrapper.find('[role="dialog"]')
    const titleId = dialog.attributes('aria-labelledby')
    expect(titleId).toBeTruthy()
    expect(wrapper.find(`#${titleId}`).text()).toBe('Test Modal')
  })

  it('displays title text', () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('h2').text()).toBe('Test Modal')
  })

  it('renders slot content', () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      slots: { default: '<p>Modal body</p>' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.text()).toContain('Modal body')
  })

  it('emits "close" when backdrop is clicked', async () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      global: { stubs: { Teleport: true } },
    })
    await wrapper.find('[aria-hidden="true"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits "close" when Escape key is pressed', async () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      global: { stubs: { Teleport: true } },
    })
    await wrapper.find('[role="dialog"]').trigger('keydown.esc')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits "close" when close button is clicked', async () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      global: { stubs: { Teleport: true } },
    })
    const closeBtn = wrapper.find('button[aria-label="Fermer"]')
    expect(closeBtn.exists()).toBe(true)
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('has tabindex="-1" for programmatic focus', () => {
    const wrapper = mount(BaseModal, {
      props: defaultProps,
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[role="dialog"]').attributes('tabindex')).toBe('-1')
  })
})
