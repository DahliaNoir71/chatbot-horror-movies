import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseInput from '../BaseInput.vue'

describe('BaseInput', () => {
  const defaultProps = { modelValue: '', label: 'Username' }

  it('renders label text', () => {
    const wrapper = mount(BaseInput, { props: defaultProps })
    expect(wrapper.find('label').text()).toContain('Username')
  })

  it('associates label with input via for/id', () => {
    const wrapper = mount(BaseInput, { props: defaultProps })
    const label = wrapper.find('label')
    const input = wrapper.find('input')
    expect(label.attributes('for')).toBe(input.attributes('id'))
  })

  it('emits update:modelValue on input', async () => {
    const wrapper = mount(BaseInput, { props: defaultProps })
    const input = wrapper.find('input')
    await input.setValue('hello')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    const emitted = wrapper.emitted('update:modelValue')!
    expect(emitted[emitted.length - 1]).toEqual(['hello'])
  })

  it('displays error message when error prop is set', () => {
    const wrapper = mount(BaseInput, {
      props: { ...defaultProps, error: 'Required field' },
    })
    expect(wrapper.text()).toContain('Required field')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  })

  it('has aria-invalid="true" when error is present', () => {
    const wrapper = mount(BaseInput, {
      props: { ...defaultProps, error: 'Error' },
    })
    expect(wrapper.find('input').attributes('aria-invalid')).toBe('true')
  })

  it('has aria-describedby pointing to error element id', () => {
    const wrapper = mount(BaseInput, {
      props: { ...defaultProps, error: 'Error' },
    })
    const input = wrapper.find('input')
    const errorEl = wrapper.find('[role="alert"]')
    expect(input.attributes('aria-describedby')).toBe(errorEl.attributes('id'))
  })

  it('does not show error element when no error', () => {
    const wrapper = mount(BaseInput, { props: defaultProps })
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('shows required indicator when required=true', () => {
    const wrapper = mount(BaseInput, {
      props: { ...defaultProps, required: true },
    })
    expect(wrapper.find('label').text()).toContain('*')
  })

  it('does not have aria-describedby when no error', () => {
    const wrapper = mount(BaseInput, { props: defaultProps })
    expect(wrapper.find('input').attributes('aria-describedby')).toBeUndefined()
  })
})
