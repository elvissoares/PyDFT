import numpy as np
from scipy.special import spherical_jn
# from scipy.fft import fftn, ifftn
import pyfftw
import multiprocessing
from pyfftw.interfaces.scipy_fftpack import fftn, ifftn
# Author: Elvis do A. Soares
# Github: @elvissoares
# Date: 2020-08-10
# Updated: 2020-07-27
pyfftw.config.NUM_THREADS = multiprocessing.cpu_count()
print('Number of cpu cores:',multiprocessing.cpu_count())

" The attractive Yukawa potential with the WDA approximation"

# defining the attractive potential 
def uatt(x,y,l,sigma,rcut=3.0):
    r = np.sqrt(x**2 + y**2)
    return np.where(r<sigma,-1.0, np.where(r<rcut,-np.exp(-(r-sigma)*l)/r,0.0))

def F(z):
    return (-0.25*np.log(1-2*z)-2*np.log(1-z)-1.5*z-1.0/(1-z)+1)

def dFdz(z):
    return z*(1-3*z+3*z**2)/((1-2*z)*(1-z)**2)

def d2Fdz2(z):
    return (1-5*z+11*z**2-9*z**3)/((1-2*z)**2*(1-z)**3)

def Lfunc(l,eta):
    return 12*eta*(1+2*eta+(1+0.5*eta)*l)

def Sfunc(l,eta):
    return ((1-eta)**2*L**2+6*eta*(1-eta)*l**2+18*eta**2*l-12*eta*(1+2*eta))

class YKPotential():
    def __init__(self,l,N,delta,sigma=1.0):
        self.l = l
        self.N = N
        self.delta = delta
        self.L = delta*N
        self.sigma = sigma

        self.w_hat = np.empty((self.N,self.N),dtype=np.complex64)
        self.rhobar = np.empty((self.N,self.N),dtype=np.float32)

        x = np.linspace(-self.L/2,self.L/2,self.N,)
        X,Y = np.meshgrid(x,x)
        u = uatt(X,Y,self.l,self.sigma)
        self.w_hat[:] = fftn(u/(u.sum()*delta**2))*delta**2
        print(ifftn(self.w_hat).sum().real)
        del x, u, X, Y

    def psi(self,rho,beta):
        eta = (np.pi/4)*self.sigma**2*rho
        l = self.l
        alpha0 = Lfunc(l,eta)/(l**2*(1-eta)**2)
        phi0 = (Lfunc(l,eta)*np.exp(-l)+Sfunc(l,eta))/(L**2*(1-eta)**2)
        w = 6*eta/phi0**2
        xi = l**2*(1-eta)**2*(1-np.exp(-l))/(Lfunc(l,eta)*np.exp(-l)+Sfunc(l,eta))\
            -12*eta*(1-eta)*(1-0.5*l-(1+0.5*l)*np.exp(-l))/(Lfunc(l,eta)*np.exp(-l)+Sfunc(l,eta))
        x = (1+l*xi)*w*beta/l**2
        y = xi*w*beta/l
        return (-alpha0/phi0-(L**2/(6*beta*eta))*(F(x)-F(y)-(x-y)*dFdz(y)))

    def dpsideta(self,rho,beta):
        eta = (np.pi/4)*self.sigma**2*rho
        l = self.l
        alpha0 = Lfunc(l,eta)/(l**2*(1-eta)**2)
        dalpha0deta = 12*(1+5*eta+l+2*l*eta)/(l**2*(1-eta)**3)
        phi0 = (Lfunc(l,eta)*np.exp(-l)+Sfunc(l,eta))/(L**2*(1-eta)**2)
        dphi0deta = (np.exp(-l)+l-1)*dalpha0deta/l - 6*(1+5*eta)/(l*(1-eta)**3)
        w = 6*eta/phi0**2
        xi = l**2*(1-eta)**2*(1-np.exp(-l))/(Lfunc(l,eta)*np.exp(-l)+Sfunc(l,eta))\
            -12*eta*(1-eta)*(1-0.5*l-(1+0.5*l)*np.exp(-l))/(Lfunc(l,eta)*np.exp(-l)+Sfunc(l,eta))
        dxideta = (12/(Lfunc(l,eta)*np.exp(-l)+Sfunc(l,eta))**2)*((1-np.exp(-l))**2*(1+4*eta-14*eta**2)*l**2 \
            -(1-np.exp(-2*l))*(1+eta-2*eta**2)*L**2+np.exp(-l)*(1-eta)**2*l**4 \
            -36*eta**2*(1-np.exp(-l)-l)*(1-np.exp(-l)-l*np.exp(-l))   )
        x = (1+l*xi)*w*beta/l**2
        dxdeta = beta*(w/l**2)*((1+l*xi)/eta+l*dxideta-2*(1+l*xi)*dphi0deta/phi0)
        y = xi*w*beta/l
        dydeta = beta*(w/l)*(xi/eta+dxideta-2*xi*dphi0deta/phi0)
        print(x.max(),y.max())
        return (-(dalpha0deta-alpha0*dphi0deta/phi0)/phi0+(L**2/(6*beta*eta**2))*(F(x)-F(y)-(x-y)*dFdz(y))\
            -(L**2/(6*beta*eta))*(dxdeta*(dFdz(x)-dFdz(y))-(x-y)*dydeta*d2Fdz2(y)))

    def free_energy(self,n_hat,beta):
        self.rhobar[:] = ifftn(n_hat*self.w_hat).real
        rho = ifftn(n_hat).real
        return np.sum(rho*self.psi(self.rhobar,beta))*self.delta**2
    
    def c1(self,n_hat,beta):
        self.rhobar[:] = ifftn(n_hat*self.w_hat).real
        # plt.imshow(self.rhobar.real, cmap='Greys_r')
        # plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
        # plt.show()
        rho = ifftn(n_hat).real
        aux = fftn((np.pi/4)*self.sigma**2*rho*self.dpsideta(self.rhobar,beta))
        return beta*(-self.psi(self.rhobar,beta)-ifftn(aux*self.w_hat)).real


if __name__ == "__main__":
    test1 = False #plot the potential
    test2 = False # the phase diagram by DFT
    test3 = False # the bulk phase diagram
    test4 = True # density profile

    import matplotlib.pyplot as plt
    from fire import optimize_fire2
    from fmt2d import RFFFT2D

    if test1:
        l = 1.8
        N = 128
        delta = 0.05
        L = N*delta
        ykm = YKPotential(l,N,delta)

        r = np.linspace(0.0,ykm.L/2,N//2)
        rcut = np.linspace(1.0,ykm.L/2,N)

        w = ifftn(ykm.w_hat).real
        plt.plot(np.linspace(-ykm.L/2,ykm.L/2,N),w[N//2],label='IFT')
        plt.legend(loc='upper left')
        plt.xlim(-L/2.0,L/2.0)
        plt.xlabel('$r/\\sigma$')
        plt.ylabel('$V(r)/\\epsilon$')
        plt.show()        

    if test2: 
        l = 1.8
        L = 10.24
        N = 1024
        delta = L/N

        FMT = RFFFT2D(N,delta)
        YKM = YKPotential(l,N,delta)

        print('N=',N)
        print('L=',L)

        muarray = np.linspace(-3.3157444444444444,3.0,10,endpoint=True)

        Tarray = np.array([1.1])

        output = True

        n = np.empty((N,N),dtype=np.float32)
        rhohat = np.empty((N,N),dtype=np.complex64)
        kx = np.fft.fftfreq(N, d=delta)*2*np.pi
        kcut = kx.max()/5
        Kx,Ky = np.meshgrid(kx,kx)
        def Pk(kx,ky):
            k = np.sqrt(kx**2+ky**2)
            return np.where(k>kcut,0.0, np.where(k>0,0.0001*N**2*(k)**(2)*np.random.randn(N,N),1.0*N**2))
        rhohat[:] = Pk(Kx,Ky)
        n[:] = ifftn(rhohat).real


        plt.imshow(n[N//2].real, cmap='Greys_r')
        plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
        plt.xlabel('$x$')
        plt.ylabel('$y$')
        plt.show()

        lnn1 = np.log(n) + np.log(0.05)
        lnn2 = np.log(n) + np.log(0.8)
        # lnn1 = np.load('fmt-wbii-densityfield-rho0.05-N-192.npy')
        # lnn2 = np.load('fmt-wbii-densityfield-rho0.9-N-192.npy')

        del n, rhohat, kx, Kx, Ky

        Vol = L**2

        for j in range(Tarray.size):

            T = Tarray[j]
            print('#######################################')
            print('T=',T)
            print("mu\trho\trho2\tOmega1\tOmega2")

            beta = 1.0/T #1.0/0.004 # in kBT units
            betainv = T

            for i in range(muarray.size):

                mu = muarray[i]
                
                ## The Grand Canonical Potential
                def Omega(lnn,mu):
                    n = np.float32(np.exp(lnn))
                    n_hat = fftn(n)
                    phi = FMT.Phi(n_hat)
                    FHS = (betainv)*np.sum(phi)*delta**2
                    Fid = betainv*np.sum(n*(lnn-1.0))*delta**2
                    Fykm = YKM.free_energy(n_hat,beta)
                    N = n.sum()*delta**2
                    return (Fid+FHS+Fykm-mu*N)/Vol

                def dOmegadnR(lnn,mu):
                    n = np.float32(np.exp(lnn))
                    n_hat = fftn(n)
                    dphidn = FMT.dPhidn(n_hat)
                    c1YKM = YKM.c1(n_hat,beta)
                    return n*(betainv*(lnn)  + (betainv)*dphidn - betainv*c1YKM - mu)*delta**2/Vol

                [lnnsol,Omegasol,Niter] = optimize_fire2(lnn1,Omega,dOmegadnR,mu,1.0e-13,100.0,output)
                [lnnsol2,Omegasol2,Niter] = optimize_fire2(lnn2,Omega,dOmegadnR,mu,1.0e-13,0.1,output)

                rhomean = np.exp(lnnsol).sum()*delta**2/Vol 
                rhomean2 = np.exp(lnnsol2).sum()*delta**2/Vol

                print(mu,rhomean,rhomean2,Omegasol,Omegasol2)

                np.save('ykm2d-densityfield1-lambda'+str(l)+'-T'+str(T)+'-mu'+str(mu)+'-N-'+str(N)+'.npy',np.exp(lnnsol))
                np.save('ykm2d-densityfield2-lambda'+str(l)+'-T'+str(T)+'-mu'+str(mu)+'-N-'+str(N)+'.npy',np.exp(lnnsol2))

    if test3: 
        l = 1.8
        N = 4
        delta = 0.05
        L = N*delta

        # The integral of Yukawa potential
        YKM = YKPotential(l,N,delta)
        def fykmWDA(n,beta): 
            return n*YKM.psi(n,beta)
        def dfykmWDAdn(n,beta): 
            return YKM.psi(n,beta)+n*YKM.dpsideta(n,beta)

        def fexcCS(n):
            eta = np.pi*n/4.0
            return n*eta*(4-3*eta)/((1-eta)**2)

        def dfexcCSdn(n):
            eta = np.pi*n/4.0
            return (8*eta - 9*eta*eta + 3*eta*eta*eta)/np.power(1-eta,3)

        print('N=',N)
        print('L=',L)

        muarray = np.linspace(-2.2915,2.2914,10,endpoint=True)

        Tarray = np.array([1.0])

        output = False

        n = np.ones((N,N),dtype=np.float32)
        # n[:] = 1.0 + 0.1*np.random.randn(N,N)

        lnn1 = np.log(n) + np.log(0.05)
        lnn2 = np.log(n) + np.log(0.8)

        del n

        Vol = L**2

        for j in range(Tarray.size):

            T = Tarray[j]
            print('#######################################')
            print('T=',T)
            print("mu\trho\trho2\tOmega1\tOmega2")

            beta = 1.0/T #1.0/0.004 # in kBT units
            betainv = T

            for i in range(muarray.size):

                mu = muarray[i]
                
                ## The Grand Canonical Potential
                def Omega(lnn,mu):
                    n = np.exp(lnn)
                    Omegak = (betainv*n*(lnn-1) + (betainv)*fexcCS(n) + n*YKM.psi(n,beta) - mu*n)*delta**2
                    return Omegak.sum()/Vol

                def dOmegadnR(lnn,mu):
                    n = np.exp(lnn)
                    return n*(betainv*(lnn) + (betainv)*dfexcCSdn(n) + YKM.psi(n,beta)+n*(np.pi/4.0)*YKM.dpsideta(n,beta) - mu)*delta**2/Vol

                [lnnsol,Omegasol,Niter] = optimize_fire2(lnn1,Omega,dOmegadnR,mu,1.0e-12,0.01,output)
                [lnnsol2,Omegasol2,Niter] = optimize_fire2(lnn2,Omega,dOmegadnR,mu,1.0e-12,0.01,output)

                rhomean = np.exp(lnnsol).sum()*delta**2/Vol 
                rhomean2 = np.exp(lnnsol2).sum()*delta**2/Vol

                print(mu,rhomean,rhomean2,Omegasol,Omegasol2)

    if test4: 
        l = 1.8
        L = 10.24
        N = 1024
        delta = L/N

        FMT = RFFFT2D(N,delta)
        YKM = YKPotential(l,N,delta)

        print('N=',N)
        print('L=',L)

        #mu = 7.92 # mu_b = 7.620733333333334 #rho_b = 0.8 and T = 2.0
        mu = -2.2915
        rhob = 0.6 #rho_b = 0.8 and T = 1.0

        T = 1.0
        beta = 1.0/T #1.0/0.004 # in kBT units
        betainv = T

        output = False

        n = 1.0e-16*np.ones((N,N),dtype=np.float32)
        for i in range(N):
            for j in range(N):
                r2 = delta**2*((i-N/2)**2+(j-N/2)**2)
                if r2>=1.0: n[i,j] = rhob*(1.0+ 0.1*np.random.randn())

        lnn1 = np.log(n)

        del n

        Vol = L**2
                
        ## The Grand Canonical Potential
        def Omega(lnn,mu):
            n = np.float32(np.exp(lnn))
            n_hat = fftn(n)
            phi = FMT.Phi(n_hat)
            FHS = (betainv)*np.sum(phi)*delta**2
            Fid = betainv*np.sum(n*(lnn-1.0))*delta**2
            Fykm = YKM.free_energy(n_hat,beta)
            N = n.sum()*delta**2
            return (Fid+FHS+Fykm-mu*N)/Vol

        def dOmegadnR(lnn,mu):
            n = np.float32(np.exp(lnn))
            n_hat = fftn(n)
            dphidn = FMT.dPhidn(n_hat)
            c1YKM = YKM.c1(n_hat,beta)
            return n*(betainv*(lnn)  + (betainv)*dphidn - betainv*c1YKM - mu)*delta**2/Vol

        [lnnsol,Omegasol,Niter] = optimize_fire2(lnn1,Omega,dOmegadnR,mu,1.0e-14,1.0,output)

        rho = np.exp(lnnsol)
        rhomean = rho.sum()*delta**2/Vol 

        print(mu,rhomean,Omegasol)

        # plt.imshow(rho[N//2].real/rhomean, cmap='Greys_r')
        # plt.colorbar(label='$\\rho(x,y)/\\rho_b$')
        # plt.xlabel('$x$')
        # plt.ylabel('$y$')
        # plt.show()

        r = np.linspace(-L/2,L/2,N)
        np.save('ykm2d-radialdistribution-lambda'+str(l)+'-T'+str(T)+'-rho'+str(rhob)+'-N-'+str(N)+'.npy',[r,rho[N//2].real/rhomean])