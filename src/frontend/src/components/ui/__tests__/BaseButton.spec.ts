import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from '../BaseButton.vue'

describe('BaseButton', () => {
  it('renders slot content', () => {
    const wrapper = mount(BaseButton, { slots: { default: 'Click me' } })
    expect(wrapper.text()).toContain('Click me')
  })

  it('emits "click" on click', async () => {
    const wrapper = mount(BaseButton)
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('does not emit "click" when disabled', async () => {
    const wrapper = mount(BaseButton, { props: { disabled: true } })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('does not emit "click" when loading', async () => {
    const wrapper = mount(BaseButton, { props: { loading: true } })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('shows LoadingSpinner when loading=true', () => {
    const wrapper = mount(BaseButton, { props: { loading: true } })
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
  })

  it('does not show LoadingSpinner when loading=false', () => {
    const wrapper = mount(BaseButton, { props: { loading: false } })
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('has aria-busy="true" when loading', () => {
    const wrapper = mount(BaseButton, { props: { loading: true } })
    expect(wrapper.find('button').attributes('aria-busy')).toBe('true')
  })

  it('has aria-disabled="true" when disabled', () => {
    const wrapper = mount(BaseButton, { props: { disabled: true } })
    expect(wrapper.find('button').attributes('aria-disabled')).toBe('true')
  })

  it('applies primary variant classes by default', () => {
    const wrapper = mount(BaseButton)
    const classes = wrapper.find('button').classes()
    expect(classes).toContain('bg-blood-red-600')
  })

  it('applies secondary variant classes', () => {
    const wrapper = mount(BaseButton, { props: { variant: 'secondary' } })
    const classes = wrapper.find('button').classes()
    expect(classes).toContain('bg-deep-black-600')
  })

  it('applies danger variant classes', () => {
    const wrapper = mount(BaseButton, { props: { variant: 'danger' } })
    const classes = wrapper.find('button').classes()
    expect(classes).toContain('bg-blood-red-800')
  })

  it('applies ghost variant classes', () => {
    const wrapper = mount(BaseButton, { props: { variant: 'ghost' } })
    const classes = wrapper.find('button').classes()
    expect(classes).toContain('bg-transparent')
  })

  it('applies correct size classes', () => {
    const sm = mount(BaseButton, { props: { size: 'sm' } })
    expect(sm.find('button').classes()).toContain('text-sm')

    const lg = mount(BaseButton, { props: { size: 'lg' } })
    expect(lg.find('button').classes()).toContain('text-lg')
  })
})
