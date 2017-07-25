# -*- coding: utf-8 -*-

# Copyright 2017 IBM RESEARCH. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

"""
Backend for the unroller that produces a QuantumCircuit.

Author: Andrew Cross
"""
from ._backendexception import BackendException
from ._unrollerbackend import UnrollerBackend

import qiskit.QuantumRegister
import qiskit.ClassicalRegister
import qiskit.QuantumCircuit
import qiskit.QISKitException

import sys
sys.path.append("..")
import qiskit.extensions.standard


class CircuitBackend(UnrollerBackend):
    """Backend for the unroller that produces a QuantumCircuit.

    By default, basis gates are the QX gates.
    """

    def __init__(self, basis=None):
        """Setup this backend.

        basis is a list of operation name strings.
        """
        self.creg = None
        self.cval = None
        if basis:
            self.basis = basis
        else:
            self.basis = ["cx", "u1", "u2", "u3"]
        self.gates = {}
        self.listen = True
        self.in_gate = ""
        self.circuit = QuantumCircuit()

    def set_basis(self, basis):
        """Declare the set of user-defined gates to emit.

        basis is a list of operation name strings.
        """
        self.basis = basis

    def version(self, version):
        """Ignore the version string.

        v is a version number.
        """
        pass

    def new_qreg(self, name, size):
        """Create a new quantum register.

        name = name of the register
        sz = size of the register
        """
        assert size >= 0, "invalid qreg size"
        q = QuantumRegister(name, size)
        self.circuit.add(q)

    def new_creg(self, name, size):
        """Create a new classical register.

        name = name of the register
        sz = size of the register
        """
        assert size >= 0, "invalid creg size"
        c = ClassicalRegister(name, size)
        self.circuit.add(c)

    def define_gate(self, name, gatedata):
        """Define a new quantum gate.

        We don't check that the definition and name agree.

        name is a string.
        gatedata is the AST node for the gate.
        """
        self.gates[name] = gatedata

    def u(self, arg, qubit):
        """Fundamental single qubit gate.

        arg is 3-tuple of float parameters.
        qubit is (regname,idx) tuple.
        """
        if self.listen:
            if "U" not in self.basis:
                self.basis.append("U")
            this_gate = self.circuit.u_base(arg, qubit)
            if self.creg is not None:
                this_gate.c_if(self.creg, self.cval)

    def cx(self, qubit0, qubit1):
        """Fundamental two qubit gate.

        qubit0 is (regname,idx) tuple for the control qubit.
        qubit1 is (regname,idx) tuple for the target qubit.
        """
        if self.listen:
            if "CX" not in self.basis:
                self.basis.append("CX")
            this_gate = self.circuit.cx_base(qubit0, qubit1)
            if self.creg is not None:
                this_gate.c_if(self.creg, self.cval)

    def measure(self, qubit, bit):
        """Measurement operation.

        qubit is (regname, idx) tuple for the input qubit.
        bit is (regname, idx) tuple for the output bit.
        """
        if "measure" not in self.basis:
            self.basis.append("measure")
        this_op = self.circuit.measure(qubit, bit)
        if self.creg is not None:
            this_op.c_if(self.creg, self.cval)

    def barrier(self, qubitlists):
        """Barrier instruction.

        qubitlists is a list of lists of (regname, idx) tuples.
        """
        if self.listen:
            if "barrier" not in self.basis:
                self.basis.append("barrier")
            flatlist = [qubit for qubitlist in qubitlists
                        for qubit in qubitlist]
            self.circuit.barrier(flatlist)

    def reset(self, qubit):
        """Reset instruction.

        qubit is a (regname, idx) tuple.
        """
        if "reset" not in self.basis:
            self.basis.append("reset")
        this_op = self.circuit.reset(qubit)
        if self.creg is not None:
            this_op.c_if(self.creg, self.cval)

    def set_condition(self, creg, cval):
        """Attach a current condition.

        creg is a name string.
        cval is the integer value for the test.
        """
        self.creg = creg
        self.cval = cval

    def drop_condition(self):
        """Drop the current condition."""
        self.creg = None
        self.cval = None

    def start_gate(self, name, args, qubits):
        """Begin a custom gate.

        name is name string.
        args is list of floating point parameters.
        qubits is list of (regname, idx) tuples.
        """
        if self.listen and name not in self.basis \
           and self.gates[name]["opaque"]:
            raise BackendException("opaque gate %s not in basis" % name)
        if self.listen and name in self.basis:
            self.in_gate = name
            self.listen = False
            # Gate names mapped to number of arguments and qubits
            # and method to invoke on [args, qubits]
            lut = {"ccx": [(0, 3),
                           lambda x: self.circuit.ccx(x[1][0], x[1][1],
                                                      x[1][2])],
                   "ch": [(0, 2),
                          lambda x: self.circuit.ch(x[1][0], x[1][1])],
                   "crz": [(1, 2),
                           lambda x: self.circuit.crz(x[0][0], x[1][0],
                                                      x[1][1])],
                   "cswap": [(0, 3),
                             lambda x: self.circuit.cswap(x[1][0],
                                                          x[1][1],
                                                          x[1][2])],
                   "cu1": [(1, 2),
                           lambda x: self.circuit.cu1(x[0][0], x[1][0],
                                                      x[1][1])],
                   "cu3": [(3, 2), lambda x: self.circuit.cu3(x[0][0],
                                                              x[0][1],
                                                              x[0][2],
                                                              x[1][0],
                                                              x[1][1])],
                   "cx": [(0, 2), lambda x: self.circuit.cx(x[1][0], x[1][1])],
                   "cy": [(0, 2), lambda x: self.circuit.cy(x[1][0], x[1][1])],
                   "cz": [(0, 2), lambda x: self.circuit.cz(x[1][0], x[1][1])],
                   "h": [(0, 1), lambda x: self.circuit.h(x[1][0])],
                   "id": [(0, 1), lambda x: self.circuit.iden(x[1][0])],
                   "rx": [(1, 1), lambda x: self.circuit.rx(x[0][0], x[1][0])],
                   "ry": [(1, 1), lambda x: self.circuit.ry(x[0][0], x[1][0])],
                   "rz": [(1, 1), lambda x: self.circuit.rz(x[0][0], x[1][0])],
                   "s": [(0, 1), lambda x: self.circuit.s(x[1][0])],
                   "sdg": [(0, 1), lambda x: self.circuit.s(x[1][0]).inverse()
                           ],
                   "t": [(0, 1), lambda x: self.circuit.t(x[1][0]).inverse()],
                   "tdg": [(0, 1), lambda x: self.circuit.t(x[1][0]).inverse()
                           ],
                   "u1": [(1, 1), lambda x: self.circuit.u1(x[0][0], x[1][0])],
                   "u2": [(2, 1), lambda x: self.circuit.u2(x[0][0], x[0][1],
                                                            x[1][0])],
                   "u3": [(3, 1), lambda x: self.circuit.u3(x[0][0], x[0][1],
                                                            x[0][2], x[1][0])],
                   "x": [(0, 1), lambda x: self.circuit.x(x[1][0])],
                   "y": [(0, 1), lambda x: self.circuit.y(x[1][0])],
                   "z": [(0, 1), lambda x: self.circuit.z(x[1][0])],
                   }
            if name not in lut:
                raise BackendException("gate %s not in standard extensions" %
                                       name)
            gate_data = lut[name]
            if gate_data[0] != (len(args), len(qubits)):
                raise BackendException("gate %s signature (%d, %d) is " %
                                       (name, len(args), len(qubits)) +
                                       "incompatible with the standard " +
                                       "extensions")
            this_gate = gate_data[1]([args, qubits])
            if self.creg is not None:
                this_gate.c_if(self.creg, self.cval)

    def end_gate(self, name, args, qubits):
        """End a custom gate.

        name is name string.
        args is list of floating point parameters.
        qubits is list of (regname, idx) tuples.
        """
        if name == self.in_gate:
            self.in_gate = ""
            self.listen = True

    def get_output(self):
        """Return the QuantumCircuit object."""
        return self.circuit
