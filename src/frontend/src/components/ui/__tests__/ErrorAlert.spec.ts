import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ErrorAlert from '../ErrorAlert.vue'

describe('ErrorAlert', () => {
  it('renders message text', () => {
    const wrapper = mount(ErrorAlert, {
      props: { message: 'Something went wrong' },
    })
    expect(wrapper.text()).toContain('Something went wrong')
  })

  it('has role="alert" and aria-live="assertive"', () => {
    const wrapper = mount(ErrorAlert, { props: { message: 'Error' } })
    const alert = wrapper.find('[role="alert"]')
    expect(alert.exists()).toBe(true)
    expect(alert.attributes('aria-live')).toBe('assertive')
  })

  it('does not show dismiss button by default', () => {
    const wrapper = mount(ErrorAlert, { props: { message: 'Error' } })
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('shows dismiss button when dismissible=true', () => {
    const wrapper = mount(ErrorAlert, {
      props: { message: 'Error', dismissible: true },
    })
    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
    expect(button.attributes('aria-label')).toBe("Fermer l'alerte")
  })

  it('emits "dismiss" when dismiss button is clicked', async () => {
    const wrapper = mount(ErrorAlert, {
      props: { message: 'Error', dismissible: true },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })
})
