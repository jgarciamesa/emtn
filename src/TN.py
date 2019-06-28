#!/usr/bin/python3

import numpy as np
import sys, json
from scipy.linalg import expm, inv
from scipy.stats import chi2
import base_counting, fisher

def EM_TN(tolerance,json_out,print_output,N_counts = 'multinomial',test = False):
    #   p = exp(-alfaY*t)
    #   q = exp(-beta*t)
    #   r = exp(-alfaR*t)

    # N:
    #       A        C        G        T
    # A  N[0][0]  N[0][1]  N[0][2]  N[0][3]
    # C  N[1][0]  N[1][1]  N[1][2]  N[1][3]
    # G  N[2][0]  N[2][1]  N[2][2]  N[2][3]
    # T  N[3][0]  N[3][1]  N[3][2]  N[3][3]

    if(N_counts == 'multinomial' or test == True):
        # Create counts matrix from a random distribution
        temp = np.random.dirichlet(np.ones(2))
        while temp[0]<0.1 or temp[1]<0.1:
            temp = np.random.dirichlet(np.ones(2))
        freq = np.array([temp[0]/2,temp[1]/2,temp[1]/2,temp[0]/2])

        fR = freq[0]+freq[2]
        fY = freq[1]+freq[3]

        t = np.random.uniform(low=0.1,high=0.3)
        rho = np.random.normal(1,0.1)
        # rho = np.random.uniform(low=0.5,high=1.5)
        R = np.random.uniform(low=max((freq[0]*freq[2]+freq[1]*freq[3])/\
            (fR*fY),rho)+0.2, high=5.0)

        b = 1/(2*fR*fY*(1+R))
        aY = (fR*fY*R-freq[0]*freq[2]-freq[1]*freq[3])/(2*(1+R)*\
            (fY*freq[0]*freq[2]*rho+fR*freq[1]*freq[3]))
        aR = rho*aY

        r,p,q = np.exp(-t*aR),np.exp(-t*aY),np.exp(-t*b)
        print('true r,p,q',r,p,q)
        true_params = [r,p,q]

        S = TN(freq,p,q,r)
        N_counts = np.random.multinomial(1000000,np.reshape(S,16))
        N_counts = np.reshape(N_counts,(4,4))
    else:
        N_counts = readFreqMatrix(N_counts)

    piA = initialPi(0,N_counts)
    piC = initialPi(1,N_counts)
    piG = initialPi(2,N_counts)
    piT = initialPi(3,N_counts)
    piR = piA+piG
    piY = piC+piT

    # estimate initial values for p,q,r,t using TN distance formula
    p,q,r,t = initialParameters(piA,piC,piG,piT,N_counts)
    params = np.array([p,q,r])

    iteration = 0
    max_iterations = 1000
    p_val = np.inf
    info = np.ones((3,3),dtype=float)
    logLold = -np.inf
    logLnew = 1
    log_diff = np.inf

    json_data = {}
    json_data['params'] = []

    # while (p_val > tolerance and iteration < max_iterations) or iteration < 10 :
    while (log_diff > tolerance and iteration < max_iterations) or iteration < 10 :

        iteration += 1

        #E-step
        S = TN([piA,piC,piG,piT],p,q,r)
        N = N_counts/S
        s1=q*r*(N[0][0]*piA+N[2][2]*piG)
        s2=q*p*(N[1][1]*piC+N[3][3]*piT)
        s3=q*(1.0-r)/piR*((piA**2.0*N[0][0]+piG**2.0*N[2][2])+piA*piG*(N[0][2]+N[2][0]))
        s4=q*(1.0-p)/piY*((piC**2.0*N[1][1]+piT**2.0*N[3][3])+piC*piT*(N[1][3]+N[3][1]))
        s5=calcS5(N,[piA,piC,piG,piT],q)
        s6=calcS(0,2,[piA,piC,piG,piT],p,q,r,N)
        s7=calcS(2,0,[piA,piC,piG,piT],p,q,r,N)
        s8=calcS(1,3,[piA,piC,piG,piT],p,q,r,N)
        s9=calcS(3,1,[piA,piC,piG,piT],p,q,r,N)
        s10=s3
        s11=s4

        # Fisher E-step
        s_2 = fisher.fisher_E_Step(N_counts,r,p,q,[piA,piC,piG,piT,piR,piY])

        #M-step
        r=s1/(s1+s3)
        p=s2/(s2+s4)
        q=(s1+s2+s3+s4)/(s1+s2+s3+s4+s5)
        piA = (s6*(-s10+s6+s7))/((s6+s7)*(-s10-s11+s6+s7+s8+s9))
        piC = (s8*(-s11+s8+s9))/((s8+s9)*(-s10-s11+s6+s7+s8+s9))
        piG = (s7*(s10-s6-s7))/((s6+s7)*(s10+s11-s6-s7-s8-s9))
        piT = (1.0-piA-piC-piG)
        piR=piA+piG
        piY=piC+piT

        #Calculation of R,t,rho
        R,t,rho = calcParameters(piA,piC,piG,piT,p,q,r)
        logLnew=logLikelihood([piA,piC,piG,piT],p,q,r,N_counts)

        if (logLold > logLnew):
            print('LOG LIKELIHOOD ERROR. Iteration ',iteration)
            print('%d r: %.8f p: %.8f q: %.8f LogLhood: %.10f convergence: %.5e ' % \
                (iteration,r,p,q,logLnew,chisq))
            print('loglikelihood diff: ',logLnew-logLold)
            return 1

        theta_diff = np.array([p,q,r]) - params
        chisq = np.matmul(np.matmul(np.transpose(theta_diff),\
            info), theta_diff)
        p_val = chi2.cdf(chisq,3)

        info = fisher.fisher_info(r,p,q,[piA,piC,piG,piT],[s1,s2,s3,s4,s5],\
            s_2,N_counts)

        log_diff = logLnew-logLold
        logLold=logLnew
        params = np.array([p,q,r])

        if(print_output):
            print('%d r: %.8f p: %.8f q: %.8f LogLhood: %.10f p value: %.5e ' % \
                (iteration,r,p,q,logLnew,p_val))

        json_data['params'].append({"r":r, "p":p, "q":q, "LogLhood":logLnew, "p_value":p_val})
        # end of while loop

    fisher_information = fisher.fisher_info(r,p,q,[piA,piC,piG,piT],[s1,s2,s3,s4,s5],s_2,N_counts)
    if(print_output):
        print('\nfisher information:\n',fisher_information)

    # append info to output json
    json_data['chisq'] = chisq
    json_data['fisher_info'] = fisher_information.tolist()
    json_data['iterations'] = iteration

    # save data in json file
    with open(json_out,'w') as outfile:
        json.dump(json_data,outfile)

    if(test):
        diff = np.array([r,p,q]) - true_params
        x2_validation = np.matmul(np.matmul(np.transpose(diff),fisher_information), diff)
        p_val = chi2.cdf(np.matmul(np.matmul(np.transpose(diff),fisher_information), diff),3)

        with open('em_chi_values.csv','a+') as outputfile:
            outputfile.write(str(p_val)+","+str(R)+","+str(rho)+","+str(freq)+"\n")

        with open('iterations.csv','a+') as outit:
            outit.write(str(iteration)+"\n")

def TN(piVector,p,q,r):
    v = np.zeros((4,4))
    alfaK = [r,p]*2
    piK = [piVector[0]+piVector[2],piVector[1]+piVector[3]]*2
    for i in range(4):
        for j in range(4):
            v[i][j] = (alfaK[i]*q*(1.0 if (i==j) else 0) \
                       + q*(1.0-alfaK[i])*piVector[j]*\
                       (1.0 if ((i%2)==(j%2)) else 0)/piK[j] \
                       + (1.0-q)*piVector[j])*piVector[i]
    return v

def logLikelihood(piVector,p,q,r,M):
    return np.sum(np.log(TN(piVector,p,q,r))*M)

def calcS5(N,piVector,q):
    v = np.zeros((4,4))
    for i in range(4):
        for j in range(4):
            v[i][j] = (1.0-q)*piVector[j]*piVector[i]*N[i][j]
    return np.sum(v)

def calcS(i,j,piVector,p,q,r,N):
    y = np.zeros(2)
    z = np.zeros(8)
    alfaK = [r,p]*2
    piK = [piVector[0]+piVector[2],piVector[1]+piVector[3]]
    #calculate X(i,i)
    x = q*alfaK[i]*N[i][i]*piVector[i]
    #calculate Y(-,i)+Y(i,-)
    y[0] = 2.0*(q*(1.0-alfaK[i])*piVector[i]**2/piK[i%2]*N[i][i])
    y[1] = (q*(1.0-alfaK[i])*piVector[i]*piVector[j]/piK[i%2])*(N[i][j]+N[j][i])
    #calculate Z(-,i)+Z(i,-)
    for k in range(4):
        z[k*2]   = (1.0-q)*piVector[i]*piVector[k]*N[i][k]
        z[k*2+1] = (1.0-q)*piVector[k]*piVector[i]*N[k][i]
    return np.sum(y) + np.sum(z) + x

def initialPi(i,N):
    return (np.sum(N[:][i]) + np.sum(N[i][:]))/(2*np.sum(N))

def initialParameters(piA,piC,piG,piT,N):
    piR = piA+piG
    piY = piC+piT
    #auxiliar constants
    k1 = 2.0*piA*piG/piR
    k2 = 2.0*piT*piC/piY
    k3 = 2.0*(piR*piY-piA*piG*piY/piR-piT*piC*piR/piY)
    p1 = (N[0][2]+N[2][0])/np.sum(N)
    p2 = (N[1][3]+N[3][1])/np.sum(N)
    q = (N[0][1]+N[0][3]+N[1][0]+N[1][2]+N[2][1]+N[2][3]+N[3][0]+\
        N[3][2])/np.sum(N)
    w1 = 1.0-p1/k1-q/2.0*piR
    w2 = 1.0-p2/k2-q/2.0*piY
    w3 = 1.0-q/2.0*piR*piY
    if(w1<0): w1=np.e
    if(w2<0): w2=np.e
    if(w3<0): w3=np.e

    d = -k1*np.log(w1)-k2*np.log(w2)-k3*np.log(w3)
    s = -k1*np.log(w1)-k2*np.log(w2)-(k3-2*piR*piY)*np.log(w3)
    v = -2.0*piR*piY*np.log(w3)
    R = s/v
    rho = 1.0

    beta = 0.5/(piR*piY*(1.0+R))
    alfaY = (piR*piY*R-piA*piG-piC*piT)/\
        (2.0*(1.0+R)*(piY*piA*piG*rho+piR*piC*piT))
    alfaR = rho*alfaY

    p = np.exp(-alfaY*d)
    q = np.exp(-beta*d)
    r = np.exp(-alfaR*d)
    return [p,q,r,d]

def calcParameters(piA,piC,piG,piT,p,q,r):
    piR = piA + piG
    piY = piC + piT
    Ts = -2.0*np.log(r)*piA*piG/piR - 2.0*np.log(p)*piC*piT/piY \
        -2.0*np.log(q)*(piA*piG + piC*piT)       #rate of transitions
    Tv = -2.0*np.log(q)*piR*piY                  #rate of transversions
    t = Ts + Tv
    R = Ts/Tv                                    #transition/transversion ratio
    beta = 0.5/(piR*piY*(1.0+R))
    alfaR = -np.log(r)/t
    alfaY = -np.log(p)/t
    rho = alfaR/alfaY
    return [R,t,rho]

def postprints(r,p,q,piA,piC,piG,piT):
    piR = piA + piG
    piY = piC + piT
    Ts = -2.0*np.log(r)*piA*piG/piR - 2.0*np.log(p)*piC*piT/piY \
        -np.log(q)*(2.0*piA*piG + 2.0*piC*piT)   #rate of transitions
    Tv = -2*np.log(q)*piR*piY                    #rate of transversions
    t = Ts + Tv
    R = Ts/Tv                                    #transition/transversion ratio
    alfaY = -np.log(p)/t
    alfaR = -np.log(r)/t
    beta = -np.log(q)/t
    rho = alfaR/alfaY
    rate = calcRate(piA,piC,piG,piT,alfaR,alfaY,beta)
    return [t,alfaR,alfaY,beta,piA,piC,piG,piT]

def readFreqMatrix(file1):
    freq = base_counting.base_count(file1)
    freq = list(map(int,freq))
    return np.reshape(freq,(4,4))

def calcRate(piA,piC,piG,piT,alfaR,alfaY,beta):
    piR = piA + piG
    piY = piC + piT
    rate = piA*(alfaR*piG/piR+beta*piG + beta*piC + beta*piT) \
         + piG*(alfaR*piA/piR+beta*piA + beta*piC + beta*piT) \
         + piC*(beta*piA + beta*piG + alfaY*piT/piY+beta*piT) \
         + piT*(beta*piA + beta*piG + alfaY*piC/piY+beta*piC)
    return rate

def main(args):
    tolerance = np.power(10.0,-10)
    EM_TN(tolerance,readFreqMatrix(args[1]),args[2],(False if len(args)==4 else True))

if __name__ == '__main__':
    main(sys.argv)