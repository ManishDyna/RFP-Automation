import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Mail, Lock, ArrowRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useAuth } from '@/hooks/use-auth'
import { api } from '@/lib/api'

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

type LoginFormData = z.infer<typeof loginSchema>

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [isLoading, setIsLoading] = useState(false)
  const [forgotPasswordOpen, setForgotPasswordOpen] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [sendingReset, setSendingReset] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true)
    try {
      await login(data.email, data.password)
      toast.success('Login successful')
      navigate('/dashboard', { replace: true })
    } catch (error: any) {
      toast.error(error.message || 'Login failed. Please check your credentials.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleForgotPassword = async () => {
    if (!forgotEmail) {
      toast.error('Please enter your email address')
      return
    }

    setSendingReset(true)
    try {
      await api.forgotPassword(forgotEmail)
      toast.success('Reset link sent! Check your inbox.')
      setForgotPasswordOpen(false)
      setForgotEmail('')
    } catch (error: any) {
      toast.error(error.message || 'Failed to send reset link')
    } finally {
      setSendingReset(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-50 via-indigo-50/30 to-slate-100 px-4">
      {/* Combined Login Card */}
      <div className="w-full max-w-[400px]">
        <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-100 px-6 py-6">
          {/* Logo & Brand */}
          <div className="text-center mb-5">
            <div className="inline-block mb-2">
              <img src={`${import.meta.env.BASE_URL}bahra-logo.svg`} alt="Bahra Electric" className="h-10 w-auto" />
            </div>
            <h1 className="text-xl font-bold text-slate-800">RFP Automation System</h1>
          </div>

          <div className="text-center mb-4">
            <h2 className="text-lg font-semibold text-slate-800">Welcome back</h2>
            <p className="text-slate-500 text-sm">Sign in to your account</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="email" className="text-slate-700 text-sm font-medium">
                Email
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@company.com"
                  className="pl-10 h-10 bg-slate-50 border-slate-200 focus:bg-white focus:border-indigo-500 transition-all"
                  {...register('email')}
                />
              </div>
              {errors.email && (
                <p className="text-xs text-red-500">{errors.email.message}</p>
              )}
            </div>

            <div className="space-y-1">
              <Label htmlFor="password" className="text-slate-700 text-sm font-medium">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  className="pl-10 h-10 bg-slate-50 border-slate-200 focus:bg-white focus:border-indigo-500 transition-all"
                  {...register('password')}
                />
              </div>
              {errors.password && (
                <p className="text-xs text-red-500">{errors.password.message}</p>
              )}
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="remember"
                  className="border-slate-300 data-[state=checked]:bg-indigo-600 data-[state=checked]:border-indigo-600"
                />
                <label
                  htmlFor="remember"
                  className="text-sm text-slate-600 cursor-pointer select-none"
                >
                  Remember me
                </label>
              </div>
              <button
                type="button"
                onClick={() => setForgotPasswordOpen(true)}
                className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
              >
                Forgot password?
              </button>
            </div>

            <Button
              type="submit"
              className="w-full h-10 bg-indigo-600 hover:bg-indigo-700 text-white font-medium mt-1"
              size="lg"
              loading={isLoading}
            >
              Sign In
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </form>

          {/* Footer inside card */}
          <p className="text-center text-xs text-slate-400 mt-4 pt-4 border-t border-slate-100">
            <a href="#" className="hover:text-slate-600">Terms of Service</a>
            <span className="mx-2">·</span>
            <a href="#" className="hover:text-slate-600">Privacy Policy</a>
          </p>
        </div>
      </div>


      {/* Forgot Password Dialog */}
      <Dialog open={forgotPasswordOpen} onOpenChange={setForgotPasswordOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-slate-800">Reset Password</DialogTitle>
            <DialogDescription className="text-slate-500">
              Enter your email address and we'll send you a link to reset your password.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="forgot-email" className="text-slate-700">
                Email address
              </Label>
              <Input
                id="forgot-email"
                type="email"
                placeholder="you@company.com"
                value={forgotEmail}
                onChange={(e) => setForgotEmail(e.target.value)}
                className="h-11 bg-slate-50 border-slate-200 focus:bg-white focus:border-indigo-500"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => setForgotPasswordOpen(false)}
              className="border-slate-200"
            >
              Cancel
            </Button>
            <Button
              onClick={handleForgotPassword}
              loading={sendingReset}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              Send Reset Link
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
