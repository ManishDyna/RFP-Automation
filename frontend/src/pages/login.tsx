import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Mail, Lock, LogIn, ArrowRight, Shield, Zap, BarChart3 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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

  const features = [
    {
      icon: Zap,
      title: 'Automated Downloads',
      description: 'Automatically fetch RFPs from multiple portals',
    },
    {
      icon: Shield,
      title: 'Smart Submissions',
      description: 'AI-powered form filling and submission',
    },
    {
      icon: BarChart3,
      title: 'Real-time Tracking',
      description: 'Monitor all RFP activities from one dashboard',
    },
  ]

  return (
    <div className="min-h-screen flex">
      {/* Left Side - Illustration & Features */}
      <div className="hidden lg:flex lg:w-[55%] login-illustration login-pattern relative overflow-hidden">
        {/* Decorative Elements */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-violet-500/10 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col justify-center px-16 py-12 w-full">
          {/* Logo & Brand */}
          <div className="mb-12">
            <div className="flex items-center gap-4 mb-6">
              <div className="bg-white rounded-xl p-3 shadow-lg shadow-white/20">
                <img src="/bahra-logo.svg" alt="Bahra Electric" className="h-12 w-auto" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">RFP Portal</h1>
                <p className="text-slate-400 text-sm">Management System</p>
              </div>
            </div>
            <h2 className="text-4xl font-bold text-white leading-tight mb-4">
              Streamline Your<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-violet-400">
                RFP Workflow
              </span>
            </h2>
            <p className="text-slate-400 text-lg max-w-md">
              Automate downloads, manage submissions, and track progress - all from a single, powerful platform.
            </p>
          </div>

          {/* Feature Cards */}
          <div className="space-y-4">
            {features.map((feature, index) => (
              <div
                key={index}
                className="flex items-start gap-4 p-4 rounded-xl bg-white/5 backdrop-blur-sm border border-white/10 hover:bg-white/10 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-500/20 flex items-center justify-center shrink-0">
                  <feature.icon className="w-5 h-5 text-indigo-400" />
                </div>
                <div>
                  <h3 className="text-white font-semibold mb-1">{feature.title}</h3>
                  <p className="text-slate-400 text-sm">{feature.description}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Bottom Stats */}
          <div className="mt-12 flex gap-8">
            <div>
              <div className="text-3xl font-bold text-white">500+</div>
              <div className="text-slate-400 text-sm">RFPs Processed</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-white">98%</div>
              <div className="text-slate-400 text-sm">Success Rate</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-white">24/7</div>
              <div className="text-slate-400 text-sm">Automation</div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-8 bg-gradient-to-br from-slate-50 via-indigo-50/30 to-slate-100">
        <div className="w-full max-w-[420px]">
          {/* Mobile Logo */}
          <div className="lg:hidden mb-8 text-center">
            <div className="inline-flex items-center gap-3 mb-2">
              <div className="bg-white rounded-xl p-3 shadow-md border border-slate-100">
                <img src="/bahra-logo.svg" alt="Bahra Electric" className="h-10 w-auto" />
              </div>
              <span className="text-xl font-bold text-slate-800">RFP Portal</span>
            </div>
          </div>

          <Card className="shadow-xl shadow-slate-200/50 border-0 bg-white/80 backdrop-blur-sm">
            <CardHeader className="space-y-1 text-center pb-2 pt-8">
              <CardTitle className="text-2xl font-bold text-slate-800">Welcome back</CardTitle>
              <CardDescription className="text-slate-500">
                Enter your credentials to access the portal
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6 pb-8 px-8">
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-slate-700 font-medium">Email</Label>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      id="email"
                      type="email"
                      placeholder="you@company.com"
                      className="pl-11 h-11 bg-slate-50 border-slate-200 focus:bg-white focus:border-indigo-500 transition-all"
                      {...register('email')}
                    />
                  </div>
                  {errors.email && (
                    <p className="text-sm text-red-500">{errors.email.message}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password" className="text-slate-700 font-medium">Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      id="password"
                      type="password"
                      placeholder="Enter your password"
                      className="pl-11 h-11 bg-slate-50 border-slate-200 focus:bg-white focus:border-indigo-500 transition-all"
                      {...register('password')}
                    />
                  </div>
                  {errors.password && (
                    <p className="text-sm text-red-500">{errors.password.message}</p>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Checkbox id="remember" className="border-slate-300 data-[state=checked]:bg-indigo-600 data-[state=checked]:border-indigo-600" />
                    <label
                      htmlFor="remember"
                      className="text-sm text-slate-600 leading-none cursor-pointer"
                    >
                      Remember me
                    </label>
                  </div>
                  <button
                    type="button"
                    onClick={() => setForgotPasswordOpen(true)}
                    className="text-sm text-indigo-600 hover:text-indigo-700 font-medium hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>

                <Button
                  type="submit"
                  className="w-full h-11 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-medium shadow-lg shadow-indigo-500/25 transition-all"
                  size="lg"
                  loading={isLoading}
                >
                  Sign In
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </form>

              <div className="mt-6 pt-6 border-t border-slate-100">
                <p className="text-center text-sm text-slate-500">
                  Need help? Contact your system administrator
                </p>
              </div>
            </CardContent>
          </Card>

          <p className="text-center text-xs text-slate-400 mt-6">
            By signing in, you agree to our Terms of Service and Privacy Policy
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
              <Label htmlFor="forgot-email" className="text-slate-700">Email address</Label>
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
            <Button variant="outline" onClick={() => setForgotPasswordOpen(false)} className="border-slate-200">
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
