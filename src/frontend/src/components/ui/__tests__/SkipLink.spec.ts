import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SkipLink from '../SkipLink.vue'

describe('SkipLink', () => {
  it('renders an anchor with href="#main-content"', () => {
    const wrapper = mount(SkipLink)
    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('#main-content')
  })

  it('contains correct text', () => {
    const wrapper = mount(SkipLink)
    expect(wrapper.find('a').text()).toBe('Aller au contenu principal')
  })

  it('has sr-only class by default', () => {
    const wrapper = mount(SkipLink)
    expect(wrapper.find('a').classes()).toContain('sr-only')
  })
})
