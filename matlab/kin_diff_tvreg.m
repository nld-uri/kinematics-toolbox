function [u, info] = kin_diff_tvreg(x, dt, alpha, tol, maxit)
%KIN_DIFF_TVREG Total-variation regularised differentiation (Chartrand 2011), ADMM.
%   Chartrand's problem  min_u alpha*||Du||_1 + 0.5*||Au-(x-x(1))||^2  becomes,
%   with w = Au (so u = dw/dt), L1 trend filtering:
%       min_w 0.5*||w-f||^2 + (alpha/dt)*||G w||_1,   G = plain second difference
%   The ADMM system (I + rho*G'G) is pentadiagonal and CONSTANT, so it factors
%   once per rho and each sweep is a banded solve plus a soft threshold.
%
%   Solved in the original variables the Hessian A'A + alpha*L is dense and so
%   ill-conditioned that pcg stalls; the unconverged iterate then acts as extra
%   smoothing and silently changes the answer.  IRLS on the smoothed L1 stalls
%   too.  ADMM solves the exact L1 objective to a stated primal/dual tolerance.
%
%   Scale-sensitive in alpha: normalise x to unit rms before calling, rescale
%   the result after.  Use std(x,1) (normalise by N) if you are comparing
%   against numpy, whose std() default differs from MATLAB's by the N-1 factor.
if nargin < 4 || isempty(tol),   tol   = 1e-8;  end
if nargin < 5 || isempty(maxit), maxit = 20000; end
x = x(:);  n = numel(x);  f = x - x(1);
e = ones(n-2,1);
G = spdiags([e -2*e e], [0 1 2], n-2, n);
mu = alpha/dt;  GtG = G'*G;  I = speye(n);
rho = mu;  if rho <= 0, rho = 1; end
dA = decomposition(I + rho*GtG, 'chol');
z = zeros(n-2,1);  uu = zeros(n-2,1);  w = f;  conv = false;
for it = 1:maxit
    w  = dA \ (f + rho*(G'*(z-uu)));
    Gw = G*w;  zo = z;
    v  = Gw + uu;
    z  = sign(v) .* max(abs(v) - mu/rho, 0);
    uu = uu + Gw - z;
    rp = norm(Gw - z);
    rd = rho*norm(G'*(z - zo));
    ep = tol*max([norm(Gw), norm(z), 1e-300]);
    ed = tol*max(rho*norm(G'*uu), 1e-300);
    conv = (rp <= ep) && (rd <= ed);
    if conv, break; end
    if rp > 10*rd
        rho = rho*2;  uu = uu/2;  dA = decomposition(I + rho*GtG, 'chol');
    elseif rd > 10*rp
        rho = rho/2;  uu = uu*2;  dA = decomposition(I + rho*GtG, 'chol');
    end
end
info = struct('iters', it, 'converged', conv, 'rho', rho, ...
              'rp_ratio', rp/max(ep,1e-300), 'rd_ratio', rd/max(ed,1e-300));
% u = dw/dt, centred interior with one-sided ends (matches the Python port)
u = zeros(n,1);
u(2:n-1) = (w(3:n) - w(1:n-2))/(2*dt);
u(1)     = (-3*w(1) + 4*w(2) - w(3))/(2*dt);
u(n)     = ( 3*w(n) - 4*w(n-1) + w(n-2))/(2*dt);
end
