import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AiBanner from '../AiBanner.vue'

describe('AiBanner', () => {
  it('renders with role="status"', () => {
    const wrapper = mount(AiBanner)
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
  })

  it('contains AI disclosure text', () => {
    const wrapper = mount(AiBanner)
    expect(wrapper.text()).toContain('intelligence artificielle')
    expect(wrapper.text()).toContain('modèle de langage')
  })

  it('does not have a dismiss button', () => {
    const wrapper = mount(AiBanner)
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
