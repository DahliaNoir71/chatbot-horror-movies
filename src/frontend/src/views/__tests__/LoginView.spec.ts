import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'
import { AxiosError, type AxiosResponse } from 'axios'
import LoginView from '../LoginView.vue'

const mockPush = vi.fn()
const mockRoute = ref({ query: {} })

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => mockRoute.value,
  RouterLink: { template: '<a><slot /></a>' },
}))

const mockLogin = vi.fn()

vi.mock('@/stores/auth.store', () => ({
  useAuthStore: () => ({
    login: mockLogin,
  }),
}))

function mountLogin(routeQuery: Record<string, string> = {}) {
  mockRoute.value = { query: routeQuery }
  return mount(LoginView, {
    global: {
      plugins: [createPinia()],
    },
  })
}

function getInputs(wrapper: ReturnType<typeof mount>) {
  const all = wrapper.findAll('input')
  return { username: all[0]!, password: all[1]! }
}

async function fillAndSubmit(
  wrapper: ReturnType<typeof mount>,
  username = 'testuser',
  password = 'password123'
) {
  const { username: u, password: p } = getInputs(wrapper)
  await u.setValue(username)
  await p.setValue(password)
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockRoute.value = { query: {} }
  })

  describe('rendering', () => {
    it('renders heading, inputs, button, and register link', () => {
      const wrapper = mountLogin()
      expect(wrapper.find('h1').text()).toBe('Connexion')
      expect(wrapper.findAll('input')).toHaveLength(2)
      expect(wrapper.find('button').text()).toContain('Se connecter')
      expect(wrapper.text()).toContain('Créer un compte')
    })

    it('shows success message when registered=true', () => {
      const wrapper = mountLogin({ registered: 'true' })
      expect(wrapper.find('output').text()).toContain('Compte créé avec succès')
    })

    it('does not show success message without registered query', () => {
      const wrapper = mountLogin()
      expect(wrapper.find('output').exists()).toBe(false)
    })
  })

  describe('validation', () => {
    it('shows error when username is empty', async () => {
      const wrapper = mountLogin()
      await wrapper.find('form').trigger('submit')

      expect(wrapper.text()).toContain("Le nom d'utilisateur est requis")
      expect(mockLogin).not.toHaveBeenCalled()
    })

    it('shows error when password is empty', async () => {
      const wrapper = mountLogin()
      const { username } = getInputs(wrapper)
      await username.setValue('testuser')
      await wrapper.find('form').trigger('submit')

      expect(wrapper.text()).toContain('Le mot de passe est requis')
      expect(mockLogin).not.toHaveBeenCalled()
    })

    it('shows error when password is less than 8 characters', async () => {
      const wrapper = mountLogin()
      await fillAndSubmit(wrapper, 'testuser', 'short')

      expect(wrapper.text()).toContain('au moins 8 caractères')
      expect(mockLogin).not.toHaveBeenCalled()
    })

    it('does not call login when validation fails', async () => {
      const wrapper = mountLogin()
      await wrapper.find('form').trigger('submit')

      expect(mockLogin).not.toHaveBeenCalled()
    })
  })

  describe('login', () => {
    it('calls authStore.login with trimmed credentials', async () => {
      mockLogin.mockResolvedValue(undefined)
      const wrapper = mountLogin()
      await fillAndSubmit(wrapper, '  testuser  ', 'password123')

      expect(mockLogin).toHaveBeenCalledWith({
        username: 'testuser',
        password: 'password123',
      })
    })

    it('redirects to / on success by default', async () => {
      mockLogin.mockResolvedValue(undefined)
      const wrapper = mountLogin()
      await fillAndSubmit(wrapper)

      expect(mockPush).toHaveBeenCalledWith('/')
    })

    it('redirects to route.query.redirect on success', async () => {
      mockLogin.mockResolvedValue(undefined)
      const wrapper = mountLogin({ redirect: '/chat' })
      await fillAndSubmit(wrapper)

      expect(mockPush).toHaveBeenCalledWith('/chat')
    })
  })

  describe('error handling', () => {
    it('shows "Identifiants invalides" on 401', async () => {
      const axiosError = new AxiosError(
        'Unauthorized',
        '401',
        undefined,
        undefined,
        { status: 401 } as AxiosResponse
      )
      mockLogin.mockRejectedValue(axiosError)
      const wrapper = mountLogin()
      await fillAndSubmit(wrapper)

      expect(wrapper.text()).toContain('Identifiants invalides')
    })

    it('shows server connection error on network failure', async () => {
      const axiosError = new AxiosError('Network Error', 'ERR_NETWORK')
      mockLogin.mockRejectedValue(axiosError)
      const wrapper = mountLogin()
      await fillAndSubmit(wrapper)

      expect(wrapper.text()).toContain('Erreur de connexion au serveur')
    })

    it('shows generic error on other axios errors', async () => {
      const axiosError = new AxiosError(
        'Server Error',
        '500',
        undefined,
        undefined,
        { status: 500 } as AxiosResponse
      )
      mockLogin.mockRejectedValue(axiosError)
      const wrapper = mountLogin()
      await fillAndSubmit(wrapper)

      expect(wrapper.text()).toContain('Une erreur est survenue')
    })

    it('shows generic error on non-axios errors', async () => {
      mockLogin.mockRejectedValue(new Error('Something went wrong'))
      const wrapper = mountLogin()
      await fillAndSubmit(wrapper)

      expect(wrapper.text()).toContain('Une erreur est survenue')
    })

    it('dismisses error alert', async () => {
      const axiosError = new AxiosError(
        'Unauthorized',
        '401',
        undefined,
        undefined,
        { status: 401 } as AxiosResponse
      )
      mockLogin.mockRejectedValue(axiosError)
      const wrapper = mountLogin()
      await fillAndSubmit(wrapper)

      expect(wrapper.text()).toContain('Identifiants invalides')

      const errorAlert = wrapper.findComponent({ name: 'ErrorAlert' })
      await errorAlert.vm.$emit('dismiss')
      await flushPromises()

      expect(wrapper.text()).not.toContain('Identifiants invalides')
    })
  })

  describe('loading state', () => {
    it('sets loading during submit', async () => {
      let resolveLogin: () => void
      mockLogin.mockReturnValue(
        new Promise<void>((resolve) => {
          resolveLogin = resolve
        })
      )
      const wrapper = mountLogin()
      const { username, password } = getInputs(wrapper)
      await username.setValue('testuser')
      await password.setValue('password123')

      wrapper.find('form').trigger('submit')
      await flushPromises()

      const button = wrapper.findComponent({ name: 'BaseButton' })
      expect(button.props('loading')).toBe(true)

      resolveLogin!()
      await flushPromises()

      expect(button.props('loading')).toBe(false)
    })
  })
})
