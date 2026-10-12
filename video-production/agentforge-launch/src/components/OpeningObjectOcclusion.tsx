import React, { createContext, useContext } from "react";
import { useCurrentFrame } from "remotion";
import * as THREE from "three";
import { corePose } from "../utils/corePose";

const Boundary = createContext(false);

// The colorless stencil keeps data-field lines off the moving box volume.
export const OpeningObjectOcclusion: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const pose = corePose(useCurrentFrame());
  return (
    <Boundary.Provider value={true}>
      <group position={pose.center} rotation={pose.rotation} scale={pose.scale}>
        <mesh position={[0, 0, 0.1]} renderOrder={-100}>
          <boxGeometry args={[6.76, 4.16, 3 * pose.split + 0.36]} />
          <meshBasicMaterial
            colorWrite={false}
            depthWrite={false}
            depthTest={false}
            stencilWrite
            stencilRef={1}
            stencilFunc={THREE.AlwaysStencilFunc}
            stencilFail={THREE.ReplaceStencilOp}
            stencilZFail={THREE.ReplaceStencilOp}
            stencilZPass={THREE.ReplaceStencilOp}
          />
        </mesh>
      </group>
      {children}
    </Boundary.Provider>
  );
};

export const DataFieldMaterial: React.FC<{ color: string; opacity: number }> = (
  props,
) => {
  const masked = useContext(Boundary);
  return (
    <meshBasicMaterial
      color={props.color}
      transparent
      opacity={props.opacity}
      stencilWrite={masked}
      stencilRef={1}
      stencilFunc={THREE.NotEqualStencilFunc}
      stencilFail={THREE.KeepStencilOp}
      stencilZFail={THREE.KeepStencilOp}
      stencilZPass={THREE.KeepStencilOp}
    />
  );
};
