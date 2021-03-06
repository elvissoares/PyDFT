import numpy as np
from scipy.special import spherical_jn
from scipy.ndimage import convolve1d
import pyfftw
import multiprocessing
from pyfftw.interfaces.scipy_fftpack import fft, ifft, fftn, ifftn
# Author: Elvis do A. Soares
# Github: @elvissoares
# Date: 2020-06-16
# Updated: 2020-11-06
pyfftw.config.NUM_THREADS = multiprocessing.cpu_count()

twopi = 2*np.pi

def sigmaLancsozFT(kx,ky,kz,kcut):
    return np.sinc(kx/kcut[0])*np.sinc(ky/kcut[1])*np.sinc(kz/kcut[2])

def translationFT(kx,ky,kz,a):
    return np.exp(1.0j*(kx*a[0]+ky*a[1]+kz*a[2]))

def w3FT(k,sigma=1.0):
    return np.piecewise(k,[k<=1e-6,k>1e-6],[np.pi*sigma**3/6,lambda k: (np.pi*sigma**2/k)*spherical_jn(1,0.5*sigma*k)])

def w2FT(k,sigma=1.0):
    return np.pi*sigma**2*spherical_jn(0,0.5*sigma*k)

def wtensFT(k,sigma=1.0):
    return np.pi*sigma**2*spherical_jn(2,0.5*sigma*k)

def wtensoverk2FT(k,sigma=1.0):
    return np.piecewise(k,[k*sigma<=1e-3,k*sigma>1e-3],[np.pi*sigma**4/60,lambda k:(np.pi*sigma**2/k**2)*spherical_jn(2,0.5*sigma*k)])

def phi2func(eta):
    return np.piecewise(eta,[eta<=1e-3,eta>1e-3],[lambda eta: 1+eta**2/9,lambda eta: 1+(2*eta-eta**2+2*np.log(1-eta)*(1-eta))/(3*eta)])

def phi3func(eta):
    return np.piecewise(eta,[eta<=1e-3,eta>1e-3],[lambda eta: 1-4*eta/9,lambda eta: 1-(2*eta-3*eta**2+2*eta**3+2*np.log(1-eta)*(1-eta)**2)/(3*eta**2)])

def phi1func(eta):
    return np.piecewise(eta,[eta<=1e-3,eta>1e-3],[lambda eta: 1-2*eta/9-eta**2/18,lambda eta: 2*(eta+np.log(1-eta)*(1-eta)**2)/(3*eta**2)])

def dphi1dnfunc(eta):
    return np.piecewise(eta,[eta<=1e-3,eta>1e-3],[lambda eta: -2/9-eta/9-eta**2/15.0,lambda eta: (2*(eta-2)*eta+4*(eta-1)*np.log(1-eta))/(3*eta**3)])

def dphi2dnfunc(eta):
    return np.piecewise(eta,[eta<=1e-3,eta>1e-3],[lambda eta: 2*eta/9+eta**2/6.0,lambda eta: -(2*eta+eta**2+2*np.log(1-eta))/(3*eta**2)])

def dphi3dnfunc(eta):
    return np.piecewise(eta,[eta<=1e-3,eta>1e-3],[lambda eta: -4.0/9+eta/9,lambda eta: -2*(1-eta)*(eta*(2+eta)+2*np.log(1-eta))/(3*eta**3)])

# The disponible methods are
# RF: Rosenfeld Functional
# WBI: White Bear version I (default method)
# WBII: White Bear version II

class FMT():
    def __init__(self,N,delta,sigma=1.0,method='WBI',symmetry='none'):
        self.method = method
        self.symmetry = symmetry

        if self.symmetry == 'none': 
            self.N = N
            self.delta = delta
            self.L = N*delta
            self.sigma = sigma

            self.w3_hat = np.empty((self.N[0],self.N[1],self.N[2]),dtype=np.complex64)
            self.w2_hat = np.empty((self.N[0],self.N[1],self.N[2]),dtype=np.complex64)
            self.w2vec_hat = np.empty((3,self.N[0],self.N[1],self.N[2]),dtype=np.complex64)
            self.w2tens_hat = np.empty((3,3,self.N[0],self.N[1],self.N[2]),dtype=np.complex64)

            self.n3 = np.empty((self.N[0],self.N[1],self.N[2]),dtype=np.float32)
            self.n2 = np.empty((self.N[0],self.N[1],self.N[2]),dtype=np.float32)
            self.n2vec = np.empty((3,self.N[0],self.N[1],self.N[2]),dtype=np.float32)
            self.n1vec = np.empty((3,self.N[0],self.N[1],self.N[2]),dtype=np.float32)
            self.n2tens = np.empty((3,3,self.N[0],self.N[1],self.N[2]),dtype=np.float32)
            
            kx = np.fft.fftfreq(self.N[0], d=self.delta[0])*twopi
            ky = np.fft.fftfreq(self.N[1], d=self.delta[1])*twopi
            kz = np.fft.fftfreq(self.N[2], d=self.delta[2])*twopi
            kcut = np.pi/self.delta
            Kx,Ky,Kz = np.meshgrid(kx,ky,kz,indexing ='ij')
            K = np.sqrt(Kx**2 + Ky**2 + Kz**2)
            del kx,ky,kz

            self.w3_hat[:] = w3FT(K)*sigmaLancsozFT(Kx,Ky,Kz,kcut)*translationFT(Kx,Ky,Kz,0.5*self.L)

            self.w2_hat[:] = w2FT(K)*sigmaLancsozFT(Kx,Ky,Kz,kcut)*translationFT(Kx,Ky,Kz,0.5*self.L)

            w2tens_hat = wtensFT(K)*sigmaLancsozFT(Kx,Ky,Kz,kcut)*translationFT(Kx,Ky,Kz,0.5*self.L)

            w2tensoverk2_hat = wtensoverk2FT(K)*sigmaLancsozFT(Kx,Ky,Kz,kcut)*translationFT(Kx,Ky,Kz,0.5*self.L)

            self.w2vec_hat[0] = -1.0j*Kx*self.w3_hat
            self.w2vec_hat[1] = -1.0j*Ky*self.w3_hat
            self.w2vec_hat[2] = -1.0j*Kz*self.w3_hat

            self.w2tens_hat[0,0] = -Kx*Kx*w2tensoverk2_hat+(1/3.0)*w2tens_hat
            self.w2tens_hat[0,1] = -Kx*Ky*w2tensoverk2_hat
            self.w2tens_hat[0,2] = -Kx*Kz*w2tensoverk2_hat
            self.w2tens_hat[1,1] = -Ky*Ky*w2tensoverk2_hat+(1/3.0)*w2tens_hat
            self.w2tens_hat[1,0] = -Ky*Kx*w2tensoverk2_hat
            self.w2tens_hat[1,2] = -Ky*Kz*w2tensoverk2_hat
            self.w2tens_hat[2,0] = -Kz*Kx*w2tensoverk2_hat
            self.w2tens_hat[2,1] = -Kz*Ky*w2tensoverk2_hat
            self.w2tens_hat[2,2] = -Kz*Kz*w2tensoverk2_hat+(1/3.0)*w2tens_hat

            del Kx,Ky,Kz,K, w2tens_hat, w2tensoverk2_hat

        if self.symmetry == 'planar':
            self.N = N
            self.delta = delta
            self.L = N*delta
            self.sigma = sigma

            self.w3_hat = np.empty(self.N,dtype=np.complex64)
            self.w2_hat = np.empty(self.N,dtype=np.complex64)
            self.w2vec_hat = np.empty(self.N,dtype=np.complex64)

            self.n3 = np.empty(self.N,dtype=np.float32)
            self.n2 = np.empty(self.N,dtype=np.float32)
            self.n2vec = np.empty(self.N,dtype=np.float32)
            self.n1vec = np.empty(self.N,dtype=np.float32)
            
            Kx = np.fft.fftfreq(self.N, d=self.delta)*twopi
            kcut = np.array([np.pi/self.delta,1.0,1.0])

            self.w3_hat[:] = w3FT(Kx)*sigmaLancsozFT(Kx,0.0,0.0,kcut)*translationFT(Kx,0.0,0.0,np.array([0.5*self.L,1,1]))

            self.w2_hat[:] = w2FT(Kx)*sigmaLancsozFT(Kx,0.0,0.0,kcut)*translationFT(Kx,0.0,0.0,np.array([0.5*self.L,1,1]))

            self.w2vec_hat[:] = -1.0j*Kx*self.w3_hat

            del Kx

    def weighted_densities(self,n_hat):
        if self.symmetry == 'none': 
            self.n3[:] = ifftn(n_hat*self.w3_hat).real
            self.n2[:] = ifftn(n_hat*self.w2_hat).real
            self.n2vec[0] = ifftn(n_hat*self.w2vec_hat[0]).real
            self.n2vec[1] = ifftn(n_hat*self.w2vec_hat[1]).real
            self.n2vec[2] = ifftn(n_hat*self.w2vec_hat[2]).real
            self.n1vec[0] = self.n2vec[0]/(twopi*self.sigma)
            self.n1vec[1] = self.n2vec[1]/(twopi*self.sigma)
            self.n1vec[2] = self.n2vec[2]/(twopi*self.sigma)
            self.n2tens[0,0] = ifftn(n_hat*self.w2tens_hat[0,0]).real
            self.n2tens[0,1] = ifftn(n_hat*self.w2tens_hat[0,1]).real
            self.n2tens[0,2] = ifftn(n_hat*self.w2tens_hat[0,2]).real
            self.n2tens[1,0] = ifftn(n_hat*self.w2tens_hat[1,0]).real
            self.n2tens[1,1] = ifftn(n_hat*self.w2tens_hat[1,1]).real
            self.n2tens[1,2] = ifftn(n_hat*self.w2tens_hat[1,2]).real
            self.n2tens[2,0] = ifftn(n_hat*self.w2tens_hat[2,0]).real
            self.n2tens[2,1] = ifftn(n_hat*self.w2tens_hat[2,1]).real
            self.n2tens[2,2] = ifftn(n_hat*self.w2tens_hat[2,2]).real

        if self.symmetry == 'planar':
            self.n3[:] = ifft(n_hat*self.w3_hat).real
            self.n2[:] = ifft(n_hat*self.w2_hat).real
            self.n2vec[:] = ifft(n_hat*self.w2vec_hat).real
            self.n1vec[:] = self.n2vec/(twopi*self.sigma)

        self.n0 = self.n2/(np.pi*self.sigma**2)
        self.n1 = self.n2/(twopi*self.sigma)
        self.oneminusn3 = 1-self.n3

        if self.method == 'RF' or self.method == 'WBI': 
            self.phi2 = 1.0
            self.dphi2dn3 = 0.0
        elif self.method == 'WBII': 
            self.phi2 = phi2func(self.n3)
            self.dphi2dn3 = dphi2dnfunc(self.n3)

        if self.method == 'WBI': 
            self.phi3 = phi1func(self.n3)
            self.dphi3dn3 = dphi1dnfunc(self.n3)
        elif self.method == 'WBII': 
            self.phi3 = phi3func(self.n3)
            self.dphi3dn3 = dphi3dnfunc(self.n3)
        else: 
            self.phi3 = 1.0
            self.dphi3dn3 = 0.0
        

    def Phi(self,n_hat):
        self.weighted_densities(n_hat)

        if self.symmetry == 'none':
            vTv = self.n2vec[0]*(self.n2tens[0,0]*self.n2vec[0]+self.n2tens[0,1]*self.n2vec[1]+self.n2tens[0,2]*self.n2vec[2])+self.n2vec[1]*(self.n2tens[1,0]*self.n2vec[0]+self.n2tens[1,1]*self.n2vec[1]+self.n2tens[1,2]*self.n2vec[2])+self.n2vec[2]*(self.n2tens[2,0]*self.n2vec[0]+self.n2tens[2,1]*self.n2vec[1]+self.n2tens[2,2]*self.n2vec[2])
            trT3 = self.n2tens[0,0]**3+self.n2tens[1,1]**3+self.n2tens[2,2]**3 + 3*self.n2tens[0,0]*self.n2tens[0,1]*self.n2tens[1,0]+ 3*self.n2tens[0,0]*self.n2tens[0,2]*self.n2tens[2,0]+ 3*self.n2tens[0,1]*self.n2tens[1,1]*self.n2tens[1,0]+ 3*self.n2tens[0,2]*self.n2tens[2,1]*self.n2tens[1,0]+ 3*self.n2tens[0,1]*self.n2tens[1,2]*self.n2tens[2,0]+ 3*self.n2tens[0,2]*self.n2tens[2,2]*self.n2tens[2,0]+ 3*self.n2tens[1,2]*self.n2tens[2,2]*self.n2tens[2,1]+ 3*self.n2tens[2,1]*self.n2tens[1,1]*self.n2tens[1,2]

            return (-self.n0*np.log(self.oneminusn3)+(self.phi2/self.oneminusn3)*(self.n1*self.n2-(self.n1vec[0]*self.n2vec[0]+self.n1vec[1]*self.n2vec[1]+self.n1vec[2]*self.n2vec[2])) + (self.phi3/(24*np.pi*self.oneminusn3**2))*(self.n2*self.n2*self.n2-3*self.n2*(self.n2vec[0]*self.n2vec[0]+self.n2vec[1]*self.n2vec[1]+self.n2vec[2]*self.n2vec[2])+9*vTv-4.5*trT3) ).real

        if self.symmetry == 'planar':
            return (-self.n0*np.log(self.oneminusn3)+(self.phi2/self.oneminusn3)*(self.n1*self.n2-(self.n1vec*self.n2vec)) + (self.phi3/(24*np.pi*self.oneminusn3**2))*(self.n2*self.n2*self.n2-3*self.n2*(self.n2vec*self.n2vec)) ).real

    def c1_hat(self,n_hat):
        self.weighted_densities(n_hat)

        if self.symmetry == 'none': 
            vTv = self.n2vec[0]*(self.n2tens[0,0]*self.n2vec[0]+self.n2tens[0,1]*self.n2vec[1]+self.n2tens[0,2]*self.n2vec[2])+self.n2vec[1]*(self.n2tens[1,0]*self.n2vec[0]+self.n2tens[1,1]*self.n2vec[1]+self.n2tens[1,2]*self.n2vec[2])+self.n2vec[2]*(self.n2tens[2,0]*self.n2vec[0]+self.n2tens[2,1]*self.n2vec[1]+self.n2tens[2,2]*self.n2vec[2])
            trT3 = self.n2tens[0,0]**3+self.n2tens[1,1]**3+self.n2tens[2,2]**3 + 3*self.n2tens[0,0]*self.n2tens[0,1]*self.n2tens[1,0]+ 3*self.n2tens[0,0]*self.n2tens[0,2]*self.n2tens[2,0]+ 3*self.n2tens[0,1]*self.n2tens[1,1]*self.n2tens[1,0]+ 3*self.n2tens[0,2]*self.n2tens[2,1]*self.n2tens[1,0]+ 3*self.n2tens[0,1]*self.n2tens[1,2]*self.n2tens[2,0]+ 3*self.n2tens[0,2]*self.n2tens[2,2]*self.n2tens[2,0]+ 3*self.n2tens[1,2]*self.n2tens[2,2]*self.n2tens[2,1]+ 3*self.n2tens[2,1]*self.n2tens[1,1]*self.n2tens[1,2]

            self.dPhidn0 = fftn(-np.log(self.oneminusn3 ))
            self.dPhidn1 = fftn(self.n2*self.phi2/self.oneminusn3 )
            self.dPhidn2 = fftn(self.n1*self.phi2/self.oneminusn3  + (3*self.n2*self.n2-3*(self.n2vec[0]*self.n2vec[0]+self.n2vec[1]*self.n2vec[1]+self.n2vec[2]*self.n2vec[2]))*self.phi3/(24*np.pi*self.oneminusn3**2) )

            self.dPhidn3 = fftn(self.n0/self.oneminusn3 +(self.n1*self.n2-(self.n1vec[0]*self.n2vec[0]+self.n1vec[1]*self.n2vec[1]+self.n1vec[2]*self.n2vec[2]))*(self.dphi2dn3 + self.phi2/self.oneminusn3)/self.oneminusn3 + (self.n2*self.n2*self.n2-3*self.n2*(self.n2vec[0]*self.n2vec[0]+self.n2vec[1]*self.n2vec[1]+self.n2vec[2]*self.n2vec[2])+9*vTv-4.5*trT3)*(self.dphi3dn3+2*self.phi3/self.oneminusn3)/(24*np.pi*self.oneminusn3**2) ) 

            self.dPhidn1vec0 = fftn( -self.n2vec[0]*self.phi2/self.oneminusn3 )
            self.dPhidn1vec1 = fftn( -self.n2vec[1]*self.phi2/self.oneminusn3 )
            self.dPhidn1vec2 = fftn( -self.n2vec[2]*self.phi2/self.oneminusn3 )
            self.dPhidn2vec0 = fftn( -self.n1vec[0]*self.phi2/self.oneminusn3 + (- 6*self.n2*self.n2vec[0]+18*self.n2tens[0,0]*self.n2vec[0]+ 18*self.n2tens[0,1]*self.n2vec[1]+ 18*self.n2tens[0,2]*self.n2vec[2]+self.n2vec[1]*self.n2tens[1,0]+ 18*self.n2vec[2]*self.n2tens[2,0])*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2vec1 = fftn(-self.n1vec[1]*self.phi2/self.oneminusn3 + (- 6*self.n2*self.n2vec[1]+ 18*self.n2vec[0]*self.n2tens[0,1]+ 18*self.n2vec[1]*self.n2tens[1,0]+ 18*self.n2tens[1,1]*self.n2vec[1]+ 18*self.n2tens[1,2]*self.n2vec[2]+ 18*self.n2vec[2]*self.n2tens[2,1])*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2vec2 = fftn(-self.n1vec[2]*self.phi2/self.oneminusn3 +(-6*self.n2*self.n2vec[2]+ 18*self.n2vec[0]*self.n2tens[0,2]+ 18*self.n2vec[1]*self.n2tens[1,2]+ 18*self.n2tens[2,0]*self.n2vec[0]+ 18*self.n2tens[2,1]*self.n2vec[1]+ 18*self.n2tens[2,2]*self.n2vec[2])*self.phi3/(24*np.pi*self.oneminusn3**2))

            self.dPhidn2tens00 = fftn((9*self.n2vec[0]*self.n2vec[0]-13.5*(self.n2tens[0,1]*self.n2tens[1,0]+self.n2tens[0,0]*self.n2tens[0,0]+self.n2tens[0,2]*self.n2tens[2,0]))*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2tens01 = fftn((9*self.n2vec[0]*self.n2vec[1]-13.5*(self.n2tens[0,1]*self.n2tens[1,1]+self.n2tens[0,0]*self.n2tens[0,1]+self.n2tens[0,2]*self.n2tens[2,1]))*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2tens02 = fftn((9*self.n2vec[0]*self.n2vec[2]-13.5*(self.n2tens[0,1]*self.n2tens[1,2]+self.n2tens[0,0]*self.n2tens[0,2]+self.n2tens[0,2]*self.n2tens[2,2]))*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2tens10 = fftn((9*self.n2vec[1]*self.n2vec[0]-13.5*(self.n2tens[1,1]*self.n2tens[1,0]+self.n2tens[1,0]*self.n2tens[0,0]+self.n2tens[1,2]*self.n2tens[2,0]))*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2tens11 = fftn((9*self.n2vec[1]*self.n2vec[1]-13.5*(self.n2tens[1,1]*self.n2tens[1,1]+self.n2tens[1,0]*self.n2tens[0,1]+self.n2tens[1,2]*self.n2tens[2,1]))*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2tens12 = fftn((9*self.n2vec[1]*self.n2vec[2]-13.5*(self.n2tens[1,1]*self.n2tens[1,2]+self.n2tens[1,0]*self.n2tens[0,2]+self.n2tens[1,2]*self.n2tens[2,2]))*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2tens20 = fftn((9*self.n2vec[2]*self.n2vec[0]-13.5*(self.n2tens[2,1]*self.n2tens[1,0]+self.n2tens[2,0]*self.n2tens[0,0]+self.n2tens[2,2]*self.n2tens[2,0]))*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2tens21 = fftn((9*self.n2vec[2]*self.n2vec[1]-13.5*(self.n2tens[2,1]*self.n2tens[1,1]+self.n2tens[2,0]*self.n2tens[0,1]+self.n2tens[2,2]*self.n2tens[2,1]))*self.phi3/(24*np.pi*self.oneminusn3**2))
            self.dPhidn2tens22 = fftn((9*self.n2vec[2]*self.n2vec[2]-13.5*(self.n2tens[2,1]*self.n2tens[1,2]+self.n2tens[2,0]*self.n2tens[0,2]+self.n2tens[2,2]*self.n2tens[2,2]))*self.phi3/(24*np.pi*self.oneminusn3**2))

            dPhidn_hat = (self.dPhidn2 + self.dPhidn1/(twopi*self.sigma) + self.dPhidn0/(np.pi*self.sigma**2))*self.w2_hat
            dPhidn_hat += self.dPhidn3*self.w3_hat
            dPhidn_hat -= (self.dPhidn2vec0+self.dPhidn1vec0/(twopi*self.sigma))*self.w2vec_hat[0] +(self.dPhidn2vec1+self.dPhidn1vec1/(twopi*self.sigma))*self.w2vec_hat[1] + (self.dPhidn2vec2+self.dPhidn1vec2/(twopi*self.sigma))*self.w2vec_hat[2]
            dPhidn_hat += self.dPhidn2tens00*self.w2tens_hat[0,0] + self.dPhidn2tens01*self.w2tens_hat[0,1] + self.dPhidn2tens02*self.w2tens_hat[0,2] + self.dPhidn2tens10*self.w2tens_hat[1,0] + self.dPhidn2tens11*self.w2tens_hat[1,1] + self.dPhidn2tens12*self.w2tens_hat[1,2] + self.dPhidn2tens20*self.w2tens_hat[2,0] + self.dPhidn2tens21*self.w2tens_hat[2,1] + self.dPhidn2tens22*self.w2tens_hat[2,2]

            del self.dPhidn0,self.dPhidn1,self.dPhidn2,self.dPhidn3,self.dPhidn1vec0,self.dPhidn1vec1,self.dPhidn1vec2,self.dPhidn2vec0,self.dPhidn2vec1,self.dPhidn2vec2, self.dPhidn2tens00, self.dPhidn2tens01, self.dPhidn2tens02, self.dPhidn2tens10, self.dPhidn2tens11, self.dPhidn2tens12, self.dPhidn2tens20, self.dPhidn2tens21, self.dPhidn2tens22
        
        if self.symmetry == 'planar':
            self.dPhidn0 = fft(-np.log(self.oneminusn3 ))
            self.dPhidn1 = fft(self.n2*self.phi2/self.oneminusn3 )
            self.dPhidn2 = fft(self.n1*self.phi2/self.oneminusn3  + (3*self.n2*self.n2-3*(self.n2vec*self.n2vec))*self.phi3/(24*np.pi*self.oneminusn3**2) )

            self.dPhidn3 = fft(self.n0/self.oneminusn3 +(self.n1*self.n2-(self.n1vec*self.n2vec))*(self.dphi2dn3 + self.phi2/self.oneminusn3)/self.oneminusn3 + (self.n2*self.n2*self.n2-3*self.n2*(self.n2vec*self.n2vec))*(self.dphi3dn3+2*self.phi3/self.oneminusn3)/(24*np.pi*self.oneminusn3**2) ) 

            self.dPhidn1vec0 = fft( -self.n2vec*self.phi2/self.oneminusn3 )
            self.dPhidn2vec0 = fft( -self.n1vec*self.phi2/self.oneminusn3  - self.n2*self.n2vec*self.phi3/(4*np.pi*self.oneminusn3**2))

            dPhidn_hat = (self.dPhidn2 + self.dPhidn1/(twopi*self.sigma) + self.dPhidn0/(np.pi*self.sigma**2))*self.w2_hat
            dPhidn_hat += self.dPhidn3*self.w3_hat
            dPhidn_hat -= (self.dPhidn2vec0+self.dPhidn1vec0/(twopi*self.sigma))*self.w2vec_hat

            del self.dPhidn0,self.dPhidn1,self.dPhidn2,self.dPhidn3,self.dPhidn1vec0,self.dPhidn2vec0,
        
        return (-dPhidn_hat)

    def dPhidn(self,n_hat):
        if self.symmetry == 'none':
            return ifftn(-self.c1_hat(n_hat)).real

        if self.symmetry == 'planar':
            return ifft(-self.c1_hat(n_hat)).real

    def mu(self,rhob):
        n3 = np.sum(rhob*np.pi*self.sigma**3/6)
        n2 = np.sum(rhob*np.pi*self.sigma**2)
        n1 = np.sum(rhob*self.sigma/2)
        n0 = np.sum(rhob)

        if self.method == 'RF' or self.method == 'WBI': 
            phi2 = 1.0
            dphi2dn3 = 0.0
        elif self.method == 'WBII': 
            phi2 = phi2func(n3)
            dphi2dn3 = dphi2dnfunc(n3)

        if self.method == 'WBI': 
            phi3 = phi1func(n3)
            dphi3dn3 = dphi1dnfunc(n3)
        elif self.method == 'WBII': 
            phi3 = phi3func(n3)
            dphi3dn3 = dphi3dnfunc(n3)
        else: 
            phi3 = 1.0
            dphi3dn3 = 0.0

        dPhidn0 = -np.log(1-n3)
        dPhidn1 = n2*phi2/(1-n3)
        dPhidn2 = n1*phi2/(1-n3) + (3*n2**2)*phi3/(24*np.pi*(1-n3)**2)
        dPhidn3 = n0/(1-n3) +(n1*n2)*(dphi2dn3 + phi2/(1-n3))/(1-n3) + (n2**3)*(dphi3dn3+2*phi3/(1-n3))/(24*np.pi*(1-n3)**2)

        return (dPhidn0+dPhidn1*self.sigma/2+dPhidn2*np.pi*self.sigma**2+dPhidn3*np.pi*self.sigma**3/6)

####################################################
class FMTplanar():
    def __init__(self,N,delta,species=1,sigma=np.array([1.0]),method='WBI'):
        self.method = method
        self.N = N
        self.delta = delta
        self.L = N*delta
        self.sigma = sigma
        self.species = species

        self.n3 = np.empty(self.N,dtype=np.float32)
        self.n2 = np.empty(self.N,dtype=np.float32)
        self.n2vec = np.empty(self.N,dtype=np.float32)

        self.w3 = np.zeros((self.species,self.N),dtype=np.float32)
        self.w2 = np.zeros((self.species,self.N),dtype=np.float32)
        self.w2vec = np.zeros((self.species,self.N),dtype=np.float32)
        self.c1array = np.empty((self.species,self.N),dtype=np.float32)

        for i in range(self.species):

            nsig = int(0.5*self.sigma[i]/self.delta)

            x = np.linspace(-0.5*self.sigma[i],0.5*self.sigma[i],2*nsig)
            self.w3[i,self.N//2-nsig:self.N//2+nsig] = np.pi*((0.5*self.sigma[i])**2-x**2)
            self.w2[i,self.N//2-nsig:self.N//2+nsig] = self.sigma[i]*np.pi
            self.w2vec[i,self.N//2-nsig:self.N//2+nsig] = twopi*x

    def weighted_densities(self,rho):
        self.n3[:] = convolve1d(rho[0], weights=self.w3[0], mode='nearest')*self.delta
        self.n2[:] = convolve1d(rho[0], weights=self.w2[0], mode='nearest')*self.delta
        self.n2vec[:] = convolve1d(rho[0], weights=self.w2vec[0], mode='nearest')*self.delta
        self.n1vec = self.n2vec/(twopi*self.sigma[0])
        self.n0 = self.n2/(np.pi*self.sigma[0]**2)
        self.n1 = self.n2/(twopi*self.sigma[0])
        
        for i in range(1,self.species):
            self.n3[:] += convolve1d(rho[i], weights=self.w3[i], mode='nearest')*self.delta
            n2 = convolve1d(rho[i], weights=self.w2[i], mode='nearest')*self.delta
            n2vec = convolve1d(rho[i], weights=self.w2vec[i], mode='nearest')*self.delta
            self.n2[:] += n2
            self.n2vec[:] += n2vec
            self.n1vec[:] += n2vec/(twopi*self.sigma[i])
            self.n0[:] += n2/(np.pi*self.sigma[i]**2)
            self.n1[:] += n2/(twopi*self.sigma[i])
            
        self.oneminusn3 = 1-self.n3

        if self.method == 'RF' or self.method == 'WBI': 
            self.phi2 = 1.0
            self.dphi2dn3 = 0.0
        elif self.method == 'WBII': 
            self.phi2 = phi2func(self.n3)
            self.dphi2dn3 = dphi2dnfunc(self.n3)

        if self.method == 'WBI': 
            self.phi3 = phi1func(self.n3)
            self.dphi3dn3 = dphi1dnfunc(self.n3)
        elif self.method == 'WBII': 
            self.phi3 = phi3func(self.n3)
            self.dphi3dn3 = dphi3dnfunc(self.n3)
        else:
            self.phi3 = 1.0
            self.dphi3dn3 = 0.0

    def Phi(self,rho):
        self.weighted_densities(rho)

        return -self.n0*np.log(self.oneminusn3)+(self.phi2/self.oneminusn3)*(self.n1*self.n2-(self.n1vec*self.n2vec)) + (self.phi3/(24*np.pi*self.oneminusn3**2))*(self.n2*self.n2*self.n2-3*self.n2*(self.n2vec*self.n2vec))

    def c1(self,rho):
        self.weighted_densities(rho)

        self.dPhidn0 = -np.log(self.oneminusn3 )
        self.dPhidn1 = self.n2*self.phi2/self.oneminusn3
        self.dPhidn2 = self.n1*self.phi2/self.oneminusn3  + (3*self.n2*self.n2-3*(self.n2vec*self.n2vec))*self.phi3/(24*np.pi*self.oneminusn3**2)

        self.dPhidn3 = self.n0/self.oneminusn3 +(self.n1*self.n2-(self.n1vec*self.n2vec))*(self.dphi2dn3 + self.phi2/self.oneminusn3)/self.oneminusn3 + (self.n2*self.n2*self.n2-3*self.n2*(self.n2vec*self.n2vec))*(self.dphi3dn3+2*self.phi3/self.oneminusn3)/(24*np.pi*self.oneminusn3**2)

        self.dPhidn1vec0 = -self.n2vec*self.phi2/self.oneminusn3 
        self.dPhidn2vec0 = -self.n1vec*self.phi2/self.oneminusn3  - self.n2*self.n2vec*self.phi3/(4*np.pi*self.oneminusn3**2)

        for i in range(self.species):
            self.c1array[i] = -convolve1d(self.dPhidn2 + self.dPhidn1/(twopi*self.sigma[i]) + self.dPhidn0/(np.pi*self.sigma[i]**2), weights=self.w2[i], mode='nearest')*self.delta - convolve1d(self.dPhidn3, weights=self.w3[i], mode='nearest')*self.delta + convolve1d(self.dPhidn2vec0+self.dPhidn1vec0/(twopi*self.sigma[i]), weights=self.w2vec[i], mode='nearest')*self.delta

        del self.dPhidn0,self.dPhidn1,self.dPhidn2,self.dPhidn3,self.dPhidn1vec0,self.dPhidn2vec0,
        
        return self.c1array

    def mu(self,rhob):
        n3 = np.sum(rhob*np.pi*self.sigma**3/6)
        n2 = np.sum(rhob*np.pi*self.sigma**2)
        n1 = np.sum(rhob*self.sigma/2)
        n0 = np.sum(rhob)

        if self.method == 'RF' or self.method == 'WBI': 
            phi2 = 1.0
            dphi2dn3 = 0.0
        elif self.method == 'WBII': 
            phi2 = phi2func(n3)
            dphi2dn3 = dphi2dnfunc(n3)

        if self.method == 'WBI': 
            phi3 = phi1func(n3)
            dphi3dn3 = dphi1dnfunc(n3)
        elif self.method == 'WBII': 
            phi3 = phi3func(n3)
            dphi3dn3 = dphi3dnfunc(n3)
        else: 
            phi3 = 1.0
            dphi3dn3 = 0.0

        dPhidn0 = -np.log(1-n3)
        dPhidn1 = n2*phi2/(1-n3)
        dPhidn2 = n1*phi2/(1-n3) + (3*n2**2)*phi3/(24*np.pi*(1-n3)**2)
        dPhidn3 = n0/(1-n3) +(n1*n2)*(dphi2dn3 + phi2/(1-n3))/(1-n3) + (n2**3)*(dphi3dn3+2*phi3/(1-n3))/(24*np.pi*(1-n3)**2)

        return (dPhidn0+dPhidn1*self.sigma/2+dPhidn2*np.pi*self.sigma**2+dPhidn3*np.pi*self.sigma**3/6)


####################################################
class FMTspherical():
    def __init__(self,N,delta,sigma=1.0,method='WBI'):
        self.method = method
        self.N = N
        self.delta = delta
        self.L = N*delta
        self.sigma = sigma

        self.n3 = np.empty(self.N,dtype=np.float32)
        self.n2 = np.empty(self.N,dtype=np.float32)
        self.n2vec = np.empty(self.N,dtype=np.float32)

        self.r = np.linspace(0,self.L,self.N)
        self.rmed = 0.5*self.delta + self.r


        self.nsig = int(0.5*self.sigma/self.delta)

        self.w3 = np.zeros(self.nsig,dtype=np.float32)
        self.w2 = np.zeros(self.nsig,dtype=np.float32)
        self.w2vec = np.zeros(self.nsig,dtype=np.float32)
        
        r = np.linspace(0.0,0.5*self.sigma,self.nsig)
        
        self.w3[:] = np.pi*((0.5*self.sigma)**2-r**2)
        self.w2[:] = self.sigma*np.pi
        self.w2vec[:] = twopi*r

        print(np.sum(self.w3*4*np.pi*r**2*self.delta)/(np.pi/6))

    def weighted_densities(self,rho):
        self.n3[:] = convolve1d(rho*self.rmed, weights=self.w3, mode='nearest')*self.delta/self.rmed
        self.n2[:] = convolve1d(rho*self.rmed, weights=self.w2, mode='nearest')*self.delta/self.rmed
        self.n2vec[:] = self.n3/self.rmed - convolve1d(rho*self.rmed, weights=self.w2vec, mode='nearest')*self.delta/self.rmed

        plt.plot(self.rmed,self.n3)
        plt.plot(self.rmed,self.n2)
        # plt.plot(self.r,self.n2vec)
        plt.show()

        self.n1vec = self.n2vec/(twopi*self.sigma)
        self.n0 = self.n2/(np.pi*self.sigma**2)
        self.n1 = self.n2/(twopi*self.sigma)
        self.oneminusn3 = 1-self.n3

        if self.method == 'RF' or self.method == 'WBI': 
            self.phi2 = 1.0
            self.dphi2dn3 = 0.0
        elif self.method == 'WBII': 
            self.phi2 = phi2func(self.n3)
            self.dphi2dn3 = dphi2dnfunc(self.n3)

        if self.method == 'WBI': 
            self.phi3 = phi1func(self.n3)
            self.dphi3dn3 = dphi1dnfunc(self.n3)
        elif self.method == 'WBII': 
            self.phi3 = phi3func(self.n3)
            self.dphi3dn3 = dphi3dnfunc(self.n3)
        else:
            self.phi3 = 1.0
            self.dphi3dn3 = 0.0

    def Phi(self,rho):
        self.weighted_densities(rho)

        return -self.n0*np.log(self.oneminusn3)+(self.phi2/self.oneminusn3)*(self.n1*self.n2-(self.n1vec*self.n2vec)) + (self.phi3/(24*np.pi*self.oneminusn3**2))*(self.n2*self.n2*self.n2-3*self.n2*(self.n2vec*self.n2vec))

    def dPhidn(self,rho):
        self.weighted_densities(rho)

        self.dPhidn0 = -np.log(self.oneminusn3 )
        self.dPhidn1 = self.n2*self.phi2/self.oneminusn3
        self.dPhidn2 = self.n1*self.phi2/self.oneminusn3  + (3*self.n2*self.n2-3*(self.n2vec*self.n2vec))*self.phi3/(24*np.pi*self.oneminusn3**2)

        self.dPhidn3 = self.n0/self.oneminusn3 +(self.n1*self.n2-(self.n1vec*self.n2vec))*(self.dphi2dn3 + self.phi2/self.oneminusn3)/self.oneminusn3 + (self.n2*self.n2*self.n2-3*self.n2*(self.n2vec*self.n2vec))*(self.dphi3dn3+2*self.phi3/self.oneminusn3)/(24*np.pi*self.oneminusn3**2)

        self.dPhidn1vec0 = -self.n2vec*self.phi2/self.oneminusn3 
        self.dPhidn2vec0 = -self.n1vec*self.phi2/self.oneminusn3  - self.n2*self.n2vec*self.phi3/(4*np.pi*self.oneminusn3**2)

        dPhidn = convolve1d((self.dPhidn2 + self.dPhidn1/(twopi*self.sigma) + self.dPhidn0/(np.pi*self.sigma**2))*self.r, weights=self.w2, mode='nearest')*self.delta/self.rmed
        dPhidn += convolve1d(self.dPhidn3*self.r, weights=self.w3, mode='nearest')*self.delta/self.rmed
        dPhidn += convolve1d((self.dPhidn2vec0+self.dPhidn1vec0/(twopi*self.sigma))*self.r, weights=self.w3, mode='nearest')*self.delta/(self.rmed)**2 - convolve1d((self.dPhidn2vec0+self.dPhidn1vec0/(twopi*self.sigma))*self.r, weights=self.w2vec, mode='nearest')*self.delta/self.rmed

        del self.dPhidn0,self.dPhidn1,self.dPhidn2,self.dPhidn3,self.dPhidn1vec0,self.dPhidn2vec0,
        
        return dPhidn

def Theta(x,y,z,xi,yi,zi):
    return np.where(((x-xi)**2+(y-yi)**2+(z-zi)**2)<=0.25,1.0,0.0)


##### Take a example using FMT ######
if __name__ == "__main__":

    import matplotlib.pyplot as plt
    from fire import optimize_fire2
    
    #############################
    test1 = False
    test2 = False # hard wall (1D-planar)
    test3 = False # hard wall mixture (1D-planar)
    test3a = False # hard-sphere (1D-spherical)
    test4 = False
    test5 = False # solid-fluid phase diagram (3D)
    test6 = True # free minimization a la Lutsko

    if test1:
        delta = 0.05
        N = 128
        L = N*delta
        fmt = FMT(N,delta)

        w = ifftn(fmt.w3_hat)
        x = np.linspace(-L/2,L/2,N)
        y = np.linspace(-L/2,L/2,N)
        X, Y = np.meshgrid(x,y)

        print(w.real.sum(),np.pi/6)

        wmax = np.max(w[:,:,N//2].real)

        cmap = plt.get_cmap('jet')
        # cp = ax.contourf(X, Y, w[:,:,N//2].real/wmax,20, cmap=cmap)
        # # ax.set_title(r'$\omega_3(r)=\Theta(\sigma/2-r)$')
        # fig.colorbar(cp,ticks=[0,0.2,0.4,0.6,0.8,1.0]) 
        # ax.set_xlabel(r'$x/\sigma$')
        # ax.set_ylabel(r'$y/\sigma$')
        # fig.savefig('omega3-N%d.pdf'% N, bbox_inches='tight')
        # plt.show()
        # plt.close()

        w = ifftn(fmt.w2_hat)

        wmax = np.max(w[:,:,N//2].real)

        fig = plt.figure()
        ax = fig.add_subplot(111)

        print(w.real.sum(),np.pi)
        cp2 = ax.contourf(X, Y, w[:,:,N//2].real/wmax,20, cmap=cmap)
        # ax.set_title(r'$\omega_2(r)=\delta(\sigma/2-r)$')
        fig.colorbar(cp2,ticks=[0,0.2,0.4,0.6,0.8,1.0]) 
        ax.set_xlabel(r'$x/\sigma$')
        ax.set_ylabel(r'$y/\sigma$')
        fig.savefig('omega2-N%d.pdf'% N, bbox_inches='tight')
        plt.show()
        plt.close()

    ######################################################
    if test2:
        delta = 0.01
        N = 500
        L = N*delta
        fmt = FMTplanar(N,delta)
        etaarray = np.array([0.4257,0.4783])

        nsig = int(0.5/delta)

        n = 0.8*np.ones((1,N),dtype=np.float32)
        n[0,:nsig] = 1.0e-12
        # n[N-nsig:] = 1.0e-12

        lnn = np.log(n)

        x = np.linspace(0,L,N)
            
        def Omega(lnn,mu):
            n[:] = np.exp(lnn)
            Fid = np.sum(n*(lnn-1.0))*delta
            Fex = np.sum(fmt.Phi(n)*delta)
            N = np.sum(n*delta,axis=1)
            return (Fid+Fex-np.sum(mu*N))/L

        def dOmegadnR(lnn,mu):
            n[:] = np.exp(lnn)
            dphidn = -fmt.c1(n)
            return n*(lnn + dphidn - mu)*delta/L

        for eta in etaarray:

            rhob = eta/(np.pi/6.0)
            mu = np.array([np.log(rhob) + (8*eta - 9*eta*eta + 3*eta*eta*eta)/np.power(1-eta,3)])
        
            [nsol,Omegasol,Niter] = optimize_fire2(lnn,Omega,dOmegadnR,mu,1.0e-10,0.1,True)

            n[:] = np.exp(nsol)
            nmean = np.sum(n,axis=1)*delta/L
            print('rhob=',rhob,'\n nmean = ',nmean[0],'\n Omega/N =',Omegasol)

            # np.save('fmt-rf-slitpore-eta'+str(eta)+'-N-'+str(N)+'.npy',[x,n[:,N//2,N//2]/rhob])

            # [zRF,rhoRF] = np.load('fmt-wbii-slitpore-eta'+str(eta)+'-N-'+str(N)+'.npy') 

            data = np.loadtxt('../MCdataHS/hardwall-eta'+str(eta)+'.dat')
            [xdata, rhodata] = [data[:,0],data[:,1]]
            plt.scatter(xdata,rhodata,marker='o',edgecolors='C0',facecolors='none',label='MC')
            plt.plot(x,n[0],label='DFT')
            plt.xlabel(r'$x/\sigma$')
            plt.ylabel(r'$\rho(x) \sigma^3$')
            plt.xlim(0.5,3)
            # plt.ylim(0.0,7)
            plt.legend(loc='best')
            plt.savefig('hardwall-eta'+str(eta)+'.png', bbox_inches='tight')
            plt.show()
            plt.close()

    if test3:
        delta = 0.01
        N = 1500
        L = N*delta
        sigma = np.array([1.0,3.0])
        fmt = FMTplanar(N,delta,species=2,sigma=sigma)

        n = 0.01*np.ones((2,N),dtype=np.float32)
        nsig = int(0.5*sigma[0]/delta)
        n[0,:nsig] = 1.0e-16
        nsig2 = int(0.5*sigma[1]/delta)
        n[1,:nsig2] = 1.0e-16
        # n[1] = n[1]/sigma[1]**3

        x = np.linspace(0,L,N)

        # plt.plot(x,n[0],label='DFT')
        # plt.plot(x,n[1]*sigma[1]**3,label='DFT')
        # plt.xlabel(r'$x/\sigma$')
        # plt.ylabel(r'$\rho(x) \sigma^3$')
        # plt.show()

        lnn = np.log(n)

        def Omega(lnn,mu):
            n[:] = np.exp(lnn)
            Fid = np.sum(n*(lnn-1.0))*delta
            Fex = np.sum(fmt.Phi(n)*delta)
            N = np.sum(n*delta,axis=1)
            return (Fid+Fex-np.sum(mu*N))/L

        def dOmegadnR(lnn,mu):
            n[:] = np.exp(lnn)
            dphidn = -fmt.c1(n)
            muarray = np.ones((2,N),dtype=np.float32)
            muarray[0] = mu[0]
            muarray[1] = mu[1]
            return n*(lnn + dphidn - muarray)*delta/L

        eta = 0.12
        x1 = 0.83
        r = sigma[0]/sigma[1]
        rhob = np.array([eta/(np.pi*sigma[0]**3*(1+(1-x1)/x1/r**3)/6), eta/(np.pi*sigma[0]**3*(1+(1-x1)/x1/r**3)/6)*(1-x1)/x1])
        # mu = np.log(rhob) + np.array([1.68465,9.21796])
        mu = np.log(rhob) + np.array([0.454241,2.56751])

        print('mu =',mu)
        print('rhob=',rhob)
    
        [nsol,Omegasol,Niter] = optimize_fire2(lnn,Omega,dOmegadnR,mu,1.0e-10,0.1,True)

        n[:] = np.exp(nsol)
        nmean = np.sum(n,axis=1)*delta/L
        print('mu =',mu)
        print('rhob=',rhob,'\n nmean = ',nmean,'\n Omega/L =',Omegasol)

        # np.save('fmt-rf-slitpore-eta'+str(eta)+'-N-'+str(N)+'.npy',[x,n[:,N//2,N//2]/rhob])

        # [zRF,rhoRF] = np.load('fmt-wbii-slitpore-eta'+str(eta)+'-N-'+str(N)+'.npy') 

        # data from: NOWORYTA, JERZY P., et al. “Hard Sphere Mixtures near a Hard Wall.” Molecular Physics, vol. 95, no. 3, Oct. 1998, pp. 415–24, doi:10.1080/00268979809483175.
        data = np.loadtxt('../MCdataHS/hardwall-mixture-eta0.12-x1_0.83-ratio3-small.dat')
        [xdata, rhodata] = [data[:,0],data[:,1]]
        plt.scatter(xdata,rhodata,marker='o',edgecolors='C0',facecolors='none',label='MC')
        plt.plot(x,n[0]/rhob[0],label='DFT')
        plt.xlabel(r'$x/\sigma_1$')
        plt.ylabel(r'$g_1(x)$')
        plt.xlim(0.0,8)
        plt.ylim(0.0,1.4)
        plt.legend(loc='upper right')
        plt.savefig('hardwall-mixture-eta0.12-ratio3-small.png', bbox_inches='tight')
        plt.show()
        plt.close()

        data = np.loadtxt('../MCdataHS/hardwall-mixture-eta0.12-x1_0.83-ratio3-big.dat')
        [xdata, rhodata] = [data[:,0],data[:,1]]
        plt.scatter(xdata,rhodata,marker='o',edgecolors='C1',facecolors='none',label='MC')
        plt.plot(x,n[1]/rhob[1],'C1',label='DFT')
        plt.xlabel(r'$x/\sigma_1$')
        plt.ylabel(r'$g_2(x)$')
        plt.xlim(0.0,8)
        plt.ylim(0.0,2)
        plt.legend(loc='upper right')
        plt.savefig('hardwall-mixture-eta0.12-ratio3-big.png', bbox_inches='tight')
        plt.show()
        plt.close()

    ################################################################
    if test3a:
        delta = 0.01
        N = 300
        L = N*delta
        fmt = FMTspherical(N,delta)
        rhobarray = np.array([0.7,0.8,0.9])

        nsig = int(1.5/delta)

        n = 1.0e-16*np.ones(N,dtype=np.float32)
        n[:nsig] = 3/np.pi
        # n[N-nsig:] = 1.0e-12

        r = 0.5*delta+np.linspace(0,L,N)
        Vol = 4*np.pi*L**3/3
            
        def Omega(n,mu):
            phi = fmt.Phi(n)
            Omegak = n*(np.log(n)-1.0) + phi - mu*n
            return np.sum(4*np.pi*r**2*Omegak*delta)/Vol

        def dOmegadnR(n,mu):
            dphidn = fmt.dPhidn(n)
            return 4*np.pi*r**2*(np.log(n) + dphidn - mu)*delta/Vol

        for rhob in rhobarray:

            eta = rhob*(np.pi/6.0)
            mu = np.log(rhob) + (8*eta - 9*eta*eta + 3*eta*eta*eta)/np.power(1-eta,3)
        
            [nsol,Omegasol,Niter] = optimize_fire2(n,Omega,dOmegadnR,mu,1.0e-9,0.001,True)

            nmean = np.sum(nsol*4*np.pi*r**2*delta)/Vol
            print('rhob=',rhob,'\n nmean = ',nmean,'\n Omega/N =',Omegasol)

            # data = np.loadtxt('../MCdataHS/hardwall-eta'+str(eta)+'.dat')
            # [xdata, rhodata] = [data[:,0],data[:,1]]
            # plt.scatter(xdata,rhodata,marker='o',edgecolors='C0',facecolors='none',label='MC')
            plt.plot(r,n/rhob,label='DFT')
            plt.xlabel(r'$r/\sigma$')
            plt.ylabel(r'$g(r)$')
            plt.xlim(1.0,2.2)
            plt.ylim(0.5,6)
            plt.legend(loc='best')
            plt.savefig('hardsphere-eta'+str(eta)+'.png', bbox_inches='tight')
            plt.show()
            plt.close()
            

    if test4:
        L = 6.4
        eta = 0.4783
        rhob = eta/(np.pi/6.0)
        mu = np.log(rhob) + (8*eta - 9*eta*eta + 3*eta*eta*eta)/np.power(1-eta,3)

        Narray = np.array([64,128,256])

        for N in Narray:
            print("Doing the N=%d"% N) 
            delta = L/N
            
            fmt = FMT(N,delta)

            n0 = 1.0e-12*np.ones((N,N,N),dtype=np.float32)
            for i in range(N):
                for j in range(N):
                    for k in range(N):
                        r2 = delta**2*((i-N/2)**2+(j-N/2)**2+(k-N/2)**2)
                        if r2>=1.0: n0[i,j,k] = rhob

            # n0 = rhob*np.ones((N,N,N),dtype=np.float32)
            # n0[27:37,:,:] = 1.0e-12
            # n0 = rhob + 0.2*np.random.randn(N,N,N)

            # n_hat = fftn(n0)
            # plt.imshow(n0[:,:,N//2], cmap='Greys_r')
            # plt.colorbar(label='$\\rho(x,y,0)/\\rho_b$')
            # # plt.xlabel('$x$')
            # # plt.ylabel('$y$')
            # plt.show()

            z = np.linspace(-L/2,L/2,N)
            
            def Omega(lnn,mu):
                n = np.exp(lnn)
                n_hat = fftn(n)
                phi = fmt.Phi(n_hat)
                del n_hat
                Omegak = n*(lnn-1.0) + phi - mu*n
                return Omegak.sum()*delta**3/L**3

            def dOmegadnR(lnn,mu):
                n = np.exp(lnn)
                n_hat = fftn(n)
                dphidn = fmt.dPhidn(n_hat)
                del n_hat
                return n*(lnn + dphidn - mu)*delta**3/L**3
            
            lnn = np.log(n0)
            
            [nsol,Omegasol,Niter] = optimize_fire2(lnn,Omega,dOmegadnR,mu,1.0e-12,1.0,True)

            n = np.exp(nsol)

            rhobcalc = n.mean()

            np.save('fmt-wbii-densityfield-eta'+str(eta)+'-N-'+str(N)+'.npy',n)

            plt.imshow(n[:,:,N//2]/rhobcalc, cmap='Greys_r')
            plt.colorbar(label=r'$\rho(x,y,0)/\rho_b$')
            plt.xlabel('$x/\\sigma$')
            plt.ylabel('$y/\\sigma$')
            plt.savefig('densitymap-N%d.pdf'% N, bbox_inches='tight')
            # plt.show()
            plt.close()

            plt.plot(z,n[:,N//2,N//2]/rhobcalc)
            plt.xlabel(r'$x/\sigma$')
            plt.ylabel(r'$\rho(x,0,0)/\rho_b$')
            # plt.xlim(0.5,3)
            # plt.ylim(0.0,5)
            plt.savefig('densityprofile-N%d.pdf'% N, bbox_inches='tight')
            # plt.show()
            plt.close()
    
    if test5: 
        # a = 1.0 #sc
        a = np.sqrt(2) # fcc
        # a = 2*np.sqrt(3)/3 #bcc
        a = 1.0 #hcp
        N = 64
        Narray = np.array([N,N,N])
        delta = 0.05
        # delta = 2*a/N
        
        deltaarray = np.array([delta,delta,delta])

        L = deltaarray*Narray
        Vol = L[0]*L[1]*L[2]

        FMT = FMT(Narray,deltaarray)

        print('The fluid-solid phase diagram')
        print('N=',N)
        print('L=',L)
        print('delta=',delta)

        # define the variables to the gaussian parametrization
        # R = a*np.array([[1,0,0],[0,1,0],[0,0,1]]) #sc
        # R = 0.5*a*np.array([[0,1,1],[1,0,1],[1,1,0]]) #fcc
        # R = 0.5*a*np.array([[1,1,-1],[-1,1,1],[1,-1,1]]) #bcc
        R = 0.5*a*np.array([[0,0,2],[1,np.sqrt(3),0],[-1,np.sqrt(3),0]]) #hcp
        def gaussian(alpha,x,y,z):
            rho = 1e-16*np.ones((N,N,N),dtype=np.float32)
            for n1 in range(-3,4):
                for n2 in range(-3,4):
                    for n3 in range(-3,4):
                        # rho += np.power(alpha/np.pi,1.5)*np.exp(-alpha*((x-n1*R[0,0]-n2*R[1,0]-n3*R[2,0])**2+(y-n1*R[0,1]-n2*R[1,1]-n3*R[2,1])**2+(z-n1*R[0,2]-n2*R[1,2]-n3*R[2,2])**2))
                        rho += (6/np.pi)*Theta(x,y,z,n1*R[0,0]+n2*R[1,0]+n3*R[2,0],n1*R[0,1]+n2*R[1,1]+n3*R[2,1],n1*R[0,2]+n2*R[1,2]+n3*R[2,2])
            return rho 

        n = np.empty((N,N,N),dtype=np.float32)
        n_hat = np.empty((N,N,N),dtype=np.complex64)

        x = np.linspace(-L[0]/2,L[0]/2,N)
        X,Y,Z = np.meshgrid(x,x,x)
        
        n[:] = gaussian(50.0,X,Y,Z)
        rhomean = n.sum()*delta**3/Vol 
        print(rhomean)
        nsig = int(0.5*a/delta)
        plt.imshow(n[N//2].real, cmap='viridis')
        plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
        plt.xlabel('$x$')
        plt.ylabel('$y$')
        plt.show()

        lnnsol = np.log(n)

        # lnnflu = np.log(n) - np.log(rhomean) + np.log(0.7)
        
        lnnflu = np.log(0.7)*np.ones((N,N,N),dtype=np.float32)

        n[:] = np.exp(lnnflu)
        rhomean = n.sum()*delta**3/Vol 
        print(rhomean)
        plt.imshow(n[N-1].real, cmap='viridis')
        plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
        plt.xlabel('$x$')
        plt.ylabel('$y$')
        plt.show()

        rhob = 0.8
        eta = rhob*np.pi/6.0
        mumin = np.log(rhob) + FMT.mu(rhob)

        rhob = 1.0
        eta = rhob*np.pi/6.0
        mumax = np.log(rhob) + FMT.mu(rhob)

        muarray = np.linspace(15.75,17,10,endpoint=True)
        # muarray = np.array([15.74,15.75,15.76])

        output = True

        ## The Grand Canonical Potential
        def Omega(lnn,mu):
            n[:] = np.exp(lnn)
            n_hat[:] = fftn(n)
            phi = FMT.Phi(n_hat)
            FHS = np.sum(phi)*delta**3
            Fid = np.sum(n*(lnn-1.0))*delta**3
            N = n.sum()*delta**3
            return (Fid+FHS-mu*N)/Vol

        def dOmegadnR(lnn,mu):
            n[:] = np.exp(lnn)
            n_hat[:] = fftn(n)
            dphidn = FMT.dPhidn(n_hat)
            return n*(lnn + dphidn - mu)*delta**3/Vol

        print('#######################################')
        print("mu\trho\trho2\tOmega1\tOmega2")

        for i in range(muarray.size):

            mu = muarray[i]

            [lnn1,Omegasol,Niter] = optimize_fire2(lnnflu,Omega,dOmegadnR,mu,5.0e-10,1.0,output)

            plt.imshow(n[N//2].real, cmap='Greys_r')
            plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
            plt.xlabel('$x$')
            plt.ylabel('$y$')
            plt.show()

            [lnn2,Omegasol2,Niter] = optimize_fire2(lnnsol,Omega,dOmegadnR,mu,5.0e-10,1.0,output)

            rhomean = np.exp(lnn1).sum()*delta**3/Vol
            rhomean2 = np.exp(lnn2).sum()*delta**3/Vol

            plt.imshow(n[N//2].real, cmap='Greys_r')
            plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
            plt.xlabel('$x$')
            plt.ylabel('$y$')
            plt.show()

            print(mu,rhomean,rhomean2,Omegasol,Omegasol2)

    if test6: 
        # a = 1.0 #sc
        a = np.sqrt(2) # fcc
        # a = 2*np.sqrt(3)/3 #bcc
        # a = 1.0 #hcp
        
        delta = 0.01
        deltaarray = np.array([delta,delta,delta])
        Narr = np.array([127,128,129,130,131,132,133,134,135])

        print('#######################################')
        print("mu\trho\tOmega")

        for N in Narr: 

            Narray = np.array([N,N,N])

            L = deltaarray*Narray
            Vol = L[0]*L[1]*L[2]

            n = np.empty((N,N,N),dtype=np.float32)
            n_hat = np.empty((N,N,N),dtype=np.complex64)

            fmt = FMT(Narray,deltaarray)

            # print('The fluid-solid phase diagram')
            print('N=',N)
            # print('L=',L)
            # print('delta=',delta)

            # define the variables to the gaussian parametrization
            # R = a*np.array([[1,0,0],[0,1,0],[0,0,1]]) #sc
            R = 0.5*a*np.array([[0,1,1],[1,0,1],[1,1,0]]) #fcc
            # R = 0.5*a*np.array([[1,1,-1],[-1,1,1],[1,-1,1]]) #bcc
            # R = 0.5*a*np.array([[0,0,2],[1,np.sqrt(3),0],[-1,np.sqrt(3),0]]) #hcp
            def gaussian(alpha,x,y,z):
                rho = 1e-16*np.ones((N,N,N),dtype=np.float32)
                for n1 in range(-3,4):
                    for n2 in range(-3,4):
                        for n3 in range(-3,4):
                            # rho += np.power(alpha/np.pi,1.5)*np.exp(-alpha*((x-n1*R[0,0]-n2*R[1,0]-n3*R[2,0])**2+(y-n1*R[0,1]-n2*R[1,1]-n3*R[2,1])**2+(z-n1*R[0,2]-n2*R[1,2]-n3*R[2,2])**2))
                            rho += (6/np.pi)*Theta(x,y,z,n1*R[0,0]+n2*R[1,0]+n3*R[2,0],n1*R[0,1]+n2*R[1,1]+n3*R[2,1],n1*R[0,2]+n2*R[1,2]+n3*R[2,2])
                return rho 

            x = np.linspace(-L[0]/2,L[0]/2,N)
            X,Y,Z = np.meshgrid(x,x,x)
            
            n[:] = gaussian(50.0,X,Y,Z)
            # rhomean = n.sum()*delta**3/Vol 
            # print(rhomean)
            # nsig = int(0.5*a/delta)
            plt.imshow(n[0].real, cmap='viridis')
            plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
            plt.xlabel('$x$')
            plt.ylabel('$y$')
            plt.show()

            lnnsol = np.log(n)

            # muarray = np.linspace(15.75,17,10,endpoint=True)
            muarray = np.array([15.75])

            output = False

            ## The Grand Canonical Potential
            def Omega(lnn,mu):
                n[:] = np.exp(lnn)
                n_hat[:] = fftn(n)
                phi = fmt.Phi(n_hat)
                FHS = np.sum(phi)*delta**3
                Fid = np.sum(n*(lnn-1.0))*delta**3
                N = n.sum()*delta**3
                return (Fid+FHS-mu*N)/Vol

            def dOmegadnR(lnn,mu):
                n[:] = np.exp(lnn)
                n_hat[:] = fftn(n)
                dphidn = fmt.dPhidn(n_hat)
                return n*(lnn + dphidn - mu)*delta**3/Vol

            for i in range(muarray.size):

                mu = muarray[i]

                [lnn2,Omegasol2,Niter] = optimize_fire2(lnnsol,Omega,dOmegadnR,mu,5.0e-10,0.2,output)

                rhomean2 = np.exp(lnn2).sum()*delta**3/Vol

                plt.imshow(n[N//2].real, cmap='Greys_r')
                plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
                plt.xlabel('$x$')
                plt.ylabel('$y$')
                plt.show()

                print(mu,rhomean2,Omegasol2)