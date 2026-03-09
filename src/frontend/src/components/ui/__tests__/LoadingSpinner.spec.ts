import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LoadingSpinner from '../LoadingSpinner.vue'

describe('LoadingSpinner', () => {
  it('renders with role="status"', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
  })

  it('has accessible label', () => {
    const wrapper = mount(LoadingSpinner)
    const status = wrapper.find('[role="status"]')
    expect(status.attributes('aria-label')).toBe('Chargement en cours')
  })

  it('contains sr-only text for screen readers', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.find('.sr-only').text()).toBe('Chargement en cours')
  })

  it('renders an SVG with animate-spin', () => {
    const wrapper = mount(LoadingSpinner)
    const svg = wrapper.find('svg')
    expect(svg.exists()).toBe(true)
    expect(svg.classes()).toContain('animate-spin')
  })

  it('applies correct size classes', () => {
    const sm = mount(LoadingSpinner, { props: { size: 'sm' } })
    expect(sm.find('svg').classes()).toContain('h-4')

    const lg = mount(LoadingSpinner, { props: { size: 'lg' } })
    expect(lg.find('svg').classes()).toContain('h-8')
  })

  it('defaults to md size', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.find('svg').classes()).toContain('h-6')
  })
})
