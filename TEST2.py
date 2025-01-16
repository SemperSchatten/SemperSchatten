#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 12 04:03:19 2025

@author: rudolf
"""

import numpy as np
from scipy.fft import fftn, ifftn
from typing import Tuple, Optional, Union
import h5py

class QuantumDynamics:
    """
    Implements quantum dynamics calculations with adaptive timestep methods,
    probability currents, and uncertainty principle verification.
    """
    def __init__(self, 
                 dimensions: int,
                 spatial_points: Union[int, Tuple[int, ...]],
                 mass: float,
                 hbar: float = 1.0):
        self.dimensions = dimensions
        self.mass = mass
        self.hbar = hbar
        
        if isinstance(spatial_points, int):
            self.spatial_points = (spatial_points,) * dimensions
        else:
            self.spatial_points = spatial_points
            
        # Set up spatial and momentum grids
        self.setup_grids()
        
    def setup_grids(self):
        """Initialize spatial and momentum grids."""
        self.dx = np.array([2*np.pi/n for n in self.spatial_points])
        self.x_grids = np.meshgrid(*[np.arange(n)*dx 
                                    for n, dx in zip(self.spatial_points, self.dx)],
                                  indexing='ij')
        
        # Momentum space grid
        self.k_grids = np.meshgrid(*[2*np.pi*np.fft.fftfreq(n, dx)
                                    for n, dx in zip(self.spatial_points, self.dx)],
                                  indexing='ij')
        
        # Kinetic energy operator in k-space
        self.T_k = sum(k**2 for k in self.k_grids) * self.hbar**2 / (2*self.mass)
        
    def solve_adaptive(self, 
                      initial_state: np.ndarray,
                      potential: callable,
                      max_dt: float,
                      tol: float,
                      num_steps: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Solve Schrödinger equation using adaptive timestep split-operator method.
        
        Args:
            initial_state: Initial wavefunction
            potential: Callable returning potential energy
            max_dt: Maximum allowed timestep
            tol: Error tolerance for adaptive stepping
            num_steps: Number of time steps
        """
        psi = initial_state
        t = 0.0
        times = [t]
        states = [psi]
        
        for _ in range(num_steps):
            # Estimate optimal timestep
            dt = self._estimate_timestep(psi, potential, max_dt, tol)
            
            # Split-operator evolution
            psi = self._split_step_evolution(psi, potential, dt)
            
            # Store results
            t += dt
            times.append(t)
            states.append(psi)
            
        return np.array(times), np.array(states)
    
    def probability_current(self, 
                          wavefunction: np.ndarray) -> np.ndarray:
        """
        Calculate probability current density j(x,t).
        
        j(x,t) = (ħ/m) Im(ψ*(x,t) ∇ψ(x,t))
        """
        gradients = np.gradient(wavefunction, *self.dx, axis=range(self.dimensions))
        
        current = []
        for grad in gradients:
            j = (self.hbar/self.mass) * np.imag(np.conjugate(wavefunction) * grad)
            current.append(j)
            
        return np.array(current)
    
    def uncertainty_product(self, 
                          wavefunction: np.ndarray) -> float:
        """
        Calculate ΔxΔp to verify uncertainty principle.
        """
        # Position uncertainty
        x_exp = sum(np.sum(x * np.abs(wavefunction)**2) * np.prod(self.dx)
                   for x in self.x_grids)
        x2_exp = sum(np.sum(x**2 * np.abs(wavefunction)**2) * np.prod(self.dx)
                    for x in self.x_grids)
        dx = np.sqrt(x2_exp - x_exp**2)
        
        # Momentum uncertainty (using FFT)
        psi_k = fftn(wavefunction)
        p_exp = sum(np.sum(k * np.abs(psi_k)**2) * np.prod(self.dx)
                   for k in self.k_grids)
        p2_exp = sum(np.sum(k**2 * np.abs(psi_k)**2) * np.prod(self.dx)
                    for k in self.k_grids)
        dp = np.sqrt(p2_exp - p_exp**2)
        
        return dx * dp
    
    def _split_step_evolution(self, 
                            psi: np.ndarray,
                            potential: callable,
                            dt: float) -> np.ndarray:
        """
        Implement split-operator method for time evolution.
        """
        # Half step in position space
        V = potential(*self.x_grids)
        psi *= np.exp(-1j * V * dt / (2 * self.hbar))
        
        # Full step in momentum space
        psi_k = fftn(psi)
        psi_k *= np.exp(-1j * self.T_k * dt / self.hbar)
        psi = ifftn(psi_k)
        
        # Final half step in position space
        psi *= np.exp(-1j * V * dt / (2 * self.hbar))
        
        return psi
    
    def _estimate_timestep(self,
                          psi: np.ndarray,
                          potential: callable,
                          max_dt: float,
                          tol: float) -> float:
        """
        Estimate optimal timestep based on energy scales.
        """
        V = potential(*self.x_grids)
        E_pot = np.sum(np.abs(psi)**2 * V) * np.prod(self.dx)
        
        psi_k = fftn(psi)
        E_kin = np.sum(np.abs(psi_k)**2 * self.T_k) * np.prod(self.dx)
        
        # Estimate based on energy scales
        dt = min(max_dt, tol * self.hbar / max(E_pot, E_kin))
        return dt